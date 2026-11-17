#include "edz_postprocess.h"
#include "edz_model_runtime.h"

#include <math.h>
#include <string.h>

typedef struct {
    edz_detection_t detection;
} candidate_t;

static float clamp01(float value) {
    if (value < 0.0f) return 0.0f;
    if (value > 1.0f) return 1.0f;
    return value;
}

static float sigmoid_stable(float value) {
    if (value >= 0.0f) {
        float z = expf(-value);
        return 1.0f / (1.0f + z);
    }
    {
        float z = expf(value);
        return z / (1.0f + z);
    }
}

static float softplus_stable(float value) {
    return log1pf(expf(-fabsf(value))) + fmaxf(value, 0.0f);
}

edz_decode_config_t edz_default_decode_config(void) {
    edz_decode_config_t config;
    config.logit_scale = EDZ_MODEL_OUTPUT_SCALE;
    config.distance_scale = EDZ_MODEL_OUTPUT_SCALE;
    config.score_threshold = 0.25f;
    config.nms_iou_threshold = 0.45f;
    config.network_width = 160u;
    config.network_height = 160u;
    config.top_k = EDZ_MAX_DETECTIONS;
    return config;
}

float edz_iou(const edz_detection_t *a, const edz_detection_t *b) {
    float left = a->x1 > b->x1 ? a->x1 : b->x1;
    float top = a->y1 > b->y1 ? a->y1 : b->y1;
    float right = a->x2 < b->x2 ? a->x2 : b->x2;
    float bottom = a->y2 < b->y2 ? a->y2 : b->y2;
    float width = right - left;
    float height = bottom - top;
    float intersection;
    float area_a;
    float area_b;
    float denominator;
    if (width <= 0.0f || height <= 0.0f) return 0.0f;
    intersection = width * height;
    area_a = (a->x2 - a->x1) * (a->y2 - a->y1);
    area_b = (b->x2 - b->x1) * (b->y2 - b->y1);
    denominator = area_a + area_b - intersection;
    return denominator > 0.0f ? intersection / denominator : 0.0f;
}

static void insert_candidate(candidate_t *items, size_t *count, size_t capacity,
                             const edz_detection_t *detection) {
    size_t position;
    size_t move_count;
    if (capacity == 0u) return;
    position = 0u;
    while (position < *count && items[position].detection.score >= detection->score)
        ++position;
    if (position >= capacity) return;
    move_count = *count < capacity ? *count - position : capacity - position - 1u;
    if (move_count != 0u)
        memmove(items + position + 1u, items + position,
                move_count * sizeof(candidate_t));
    items[position].detection = *detection;
    if (*count < capacity) ++*count;
}

static void decode_head(const int16_t *tensor, unsigned grid, unsigned stride,
                        const edz_decode_config_t *config, candidate_t *candidates,
                        size_t *candidate_count, size_t capacity) {
    unsigned y;
    unsigned x;
    for (y = 0; y < grid; ++y) {
        for (x = 0; x < grid; ++x) {
            const int16_t *cell = tensor + ((size_t)y * grid + x) * EDZ_HEAD_CHANNELS;
            float center_score = sigmoid_stable(cell[6] * config->logit_scale);
            unsigned class_id;
            for (class_id = 0; class_id < 6u; ++class_id) {
                float class_score = sigmoid_stable(cell[class_id] * config->logit_scale);
                float score = sqrtf(class_score * center_score);
                edz_detection_t detection;
                float center_x;
                float center_y;
                float left;
                float top;
                float right;
                float bottom;
                if (score < config->score_threshold) continue;
                center_x = ((float)x + 0.5f) * stride;
                center_y = ((float)y + 0.5f) * stride;
                left = softplus_stable(cell[7] * config->distance_scale) * stride;
                top = softplus_stable(cell[8] * config->distance_scale) * stride;
                right = softplus_stable(cell[9] * config->distance_scale) * stride;
                bottom = softplus_stable(cell[10] * config->distance_scale) * stride;
                detection.class_id = (uint16_t)class_id;
                detection.flags = 0u;
                detection.score = score;
                detection.x1 = clamp01((center_x - left) / config->network_width);
                detection.y1 = clamp01((center_y - top) / config->network_height);
                detection.x2 = clamp01((center_x + right) / config->network_width);
                detection.y2 = clamp01((center_y + bottom) / config->network_height);
                if (detection.x2 <= detection.x1 || detection.y2 <= detection.y1) continue;
                insert_candidate(candidates, candidate_count, capacity, &detection);
            }
        }
    }
}

size_t edz_decode_and_nms(const int16_t tensor[EDZ_HEAD_VALUE_COUNT],
                          const edz_decode_config_t *config,
                          edz_detection_t output[EDZ_MAX_DETECTIONS]) {
    candidate_t candidates[EDZ_MAX_DETECTIONS];
    size_t candidate_count = 0u;
    size_t output_count = 0u;
    size_t index;
    size_t capacity;
    if (!tensor || !config || !output || config->network_width == 0u ||
        config->network_height == 0u)
        return 0u;
    capacity = config->top_k;
    if (capacity > EDZ_MAX_DETECTIONS) capacity = EDZ_MAX_DETECTIONS;
    decode_head(tensor, 20u, 8u, config, candidates, &candidate_count, capacity);
    decode_head(tensor + 20u * 20u * EDZ_HEAD_CHANNELS, 10u, 16u, config,
                candidates, &candidate_count, capacity);
    for (index = 0u; index < candidate_count; ++index) {
        size_t kept;
        int suppressed = 0;
        for (kept = 0u; kept < output_count; ++kept) {
            if (output[kept].class_id == candidates[index].detection.class_id &&
                edz_iou(output + kept, &candidates[index].detection) >
                    config->nms_iou_threshold) {
                suppressed = 1;
                break;
            }
        }
        if (!suppressed) output[output_count++] = candidates[index].detection;
    }
    return output_count;
}
