#ifndef EDZ_POSTPROCESS_H
#define EDZ_POSTPROCESS_H

#include "edz_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

#define EDZ_HEAD_VALUE_COUNT 5500u
#define EDZ_HEAD_CHANNELS 11u

typedef struct {
    float logit_scale;
    float distance_scale;
    float score_threshold;
    float nms_iou_threshold;
    uint16_t network_width;
    uint16_t network_height;
    uint16_t top_k;
} edz_decode_config_t;

edz_decode_config_t edz_default_decode_config(void);

/* Tensor layout: 20x20x11 followed by 10x10x11, cell-major and channel-last. */
size_t edz_decode_and_nms(const int16_t tensor[EDZ_HEAD_VALUE_COUNT],
                          const edz_decode_config_t *config,
                          edz_detection_t output[EDZ_MAX_DETECTIONS]);

float edz_iou(const edz_detection_t *a, const edz_detection_t *b);

#ifdef __cplusplus
}
#endif

#endif
