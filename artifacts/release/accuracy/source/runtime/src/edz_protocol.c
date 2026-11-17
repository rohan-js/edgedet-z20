#include "edz_protocol.h"

#include <string.h>

static void put_u16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)(value >> 8);
    p[1] = (uint8_t)value;
}

static void put_u32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)(value >> 24);
    p[1] = (uint8_t)(value >> 16);
    p[2] = (uint8_t)(value >> 8);
    p[3] = (uint8_t)value;
}

static void put_u64(uint8_t *p, uint64_t value) {
    put_u32(p, (uint32_t)(value >> 32));
    put_u32(p + 4, (uint32_t)value);
}

static uint16_t get_u16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}

static uint32_t get_u32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}

static uint64_t get_u64(const uint8_t *p) {
    return ((uint64_t)get_u32(p) << 32) | get_u32(p + 4);
}

static void put_float(uint8_t *p, float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    put_u32(p, bits);
}

static float get_float(const uint8_t *p) {
    uint32_t bits = get_u32(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

uint32_t edz_crc32_init(void) { return 0xffffffffu; }

uint32_t edz_crc32_update(uint32_t state, const void *data, size_t length) {
    const uint8_t *bytes = (const uint8_t *)data;
    size_t i;
    for (i = 0; i < length; ++i) {
        unsigned bit;
        state ^= bytes[i];
        for (bit = 0; bit < 8; ++bit) {
            state = (state >> 1) ^ (0xedb88320u & (0u - (state & 1u)));
        }
    }
    return state;
}

uint32_t edz_crc32_finish(uint32_t state) { return state ^ 0xffffffffu; }

uint32_t edz_crc32(const void *data, size_t length) {
    return edz_crc32_finish(edz_crc32_update(edz_crc32_init(), data, length));
}

int edz_encode_request_header(const edz_request_header_t *h,
                              uint8_t out[EDZ_REQUEST_HEADER_SIZE]) {
    if (!h || !out) return -1;
    memcpy(out, EDZ_MAGIC, 4);
    put_u16(out + 4, h->version);
    put_u16(out + 6, h->message_type);
    put_u32(out + 8, h->frame_id);
    put_u64(out + 12, h->timestamp_us);
    put_u16(out + 20, h->width);
    put_u16(out + 22, h->height);
    put_u16(out + 24, h->stride);
    put_u16(out + 26, h->pixel_format);
    put_u32(out + 28, h->payload_length);
    put_u32(out + 32, h->crc32);
    return 0;
}

int edz_decode_request_header(const uint8_t in[EDZ_REQUEST_HEADER_SIZE],
                              edz_request_header_t *h) {
    if (!in || !h) return -1;
    if (memcmp(in, EDZ_MAGIC, 4) != 0) return EDZ_STATUS_BAD_MAGIC;
    h->version = get_u16(in + 4);
    h->message_type = get_u16(in + 6);
    h->frame_id = get_u32(in + 8);
    h->timestamp_us = get_u64(in + 12);
    h->width = get_u16(in + 20);
    h->height = get_u16(in + 22);
    h->stride = get_u16(in + 24);
    h->pixel_format = get_u16(in + 26);
    h->payload_length = get_u32(in + 28);
    h->crc32 = get_u32(in + 32);
    return 0;
}

int edz_encode_response_header(const edz_response_header_t *h,
                               uint8_t out[EDZ_RESPONSE_HEADER_SIZE]) {
    if (!h || !out) return -1;
    memcpy(out, EDZ_MAGIC, 4);
    put_u16(out + 4, h->version);
    put_u16(out + 6, h->status);
    put_u32(out + 8, h->frame_id);
    put_u64(out + 12, h->kernel_cycles);
    put_u64(out + 20, h->total_cycles);
    put_u16(out + 28, h->detection_count);
    put_u16(out + 30, h->reserved);
    put_u32(out + 32, h->dropped_frames);
    put_u32(out + 36, h->payload_length);
    put_u32(out + 40, h->crc32);
    return 0;
}

int edz_decode_response_header(const uint8_t in[EDZ_RESPONSE_HEADER_SIZE],
                               edz_response_header_t *h) {
    if (!in || !h) return -1;
    if (memcmp(in, EDZ_MAGIC, 4) != 0) return EDZ_STATUS_BAD_MAGIC;
    h->version = get_u16(in + 4);
    h->status = get_u16(in + 6);
    h->frame_id = get_u32(in + 8);
    h->kernel_cycles = get_u64(in + 12);
    h->total_cycles = get_u64(in + 20);
    h->detection_count = get_u16(in + 28);
    h->reserved = get_u16(in + 30);
    h->dropped_frames = get_u32(in + 32);
    h->payload_length = get_u32(in + 36);
    h->crc32 = get_u32(in + 40);
    return 0;
}

int edz_encode_detection(const edz_detection_t *d,
                         uint8_t out[EDZ_DETECTION_WIRE_SIZE]) {
    if (!d || !out) return -1;
    put_u16(out, d->class_id);
    put_u16(out + 2, d->flags);
    put_float(out + 4, d->score);
    put_float(out + 8, d->x1);
    put_float(out + 12, d->y1);
    put_float(out + 16, d->x2);
    put_float(out + 20, d->y2);
    return 0;
}

int edz_decode_detection(const uint8_t in[EDZ_DETECTION_WIRE_SIZE],
                         edz_detection_t *d) {
    if (!in || !d) return -1;
    d->class_id = get_u16(in);
    d->flags = get_u16(in + 2);
    d->score = get_float(in + 4);
    d->x1 = get_float(in + 8);
    d->y1 = get_float(in + 12);
    d->x2 = get_float(in + 16);
    d->y2 = get_float(in + 20);
    return 0;
}

static uint32_t message_crc(const uint8_t *header, size_t prefix_length,
                            const void *payload, size_t payload_length) {
    uint32_t state = edz_crc32_update(edz_crc32_init(), header, prefix_length);
    if (payload_length != 0 && payload != NULL) {
        state = edz_crc32_update(state, payload, payload_length);
    }
    return edz_crc32_finish(state);
}

uint32_t edz_request_crc(const uint8_t header[EDZ_REQUEST_HEADER_SIZE],
                         const void *payload, size_t length) {
    return message_crc(header, EDZ_REQUEST_HEADER_SIZE - 4u, payload, length);
}

uint32_t edz_response_crc(const uint8_t header[EDZ_RESPONSE_HEADER_SIZE],
                          const void *payload, size_t length) {
    return message_crc(header, EDZ_RESPONSE_HEADER_SIZE - 4u, payload, length);
}

edz_status_t edz_validate_request(const edz_request_header_t *h) {
    uint32_t minimum_stride;
    uint32_t expected_length;
    if (!h) return EDZ_STATUS_INTERNAL_ERROR;
    if (h->version != EDZ_PROTOCOL_VERSION) return EDZ_STATUS_BAD_VERSION;
    if (h->message_type != EDZ_MESSAGE_FRAME) return EDZ_STATUS_BAD_MESSAGE;
    if (h->pixel_format != EDZ_PIXEL_RGB888 || h->width != 320u || h->height != 320u)
        return EDZ_STATUS_BAD_DIMENSIONS;
    minimum_stride = (uint32_t)h->width * 3u;
    if (h->stride != minimum_stride) return EDZ_STATUS_BAD_DIMENSIONS;
    expected_length = (uint32_t)h->stride * h->height;
    if (h->payload_length != expected_length || h->payload_length > EDZ_MAX_FRAME_PAYLOAD)
        return EDZ_STATUS_BAD_LENGTH;
    return EDZ_STATUS_OK;
}

const char *edz_status_string(edz_status_t status) {
    switch (status) {
    case EDZ_STATUS_OK: return "ok";
    case EDZ_STATUS_BAD_MAGIC: return "bad magic";
    case EDZ_STATUS_BAD_VERSION: return "bad version";
    case EDZ_STATUS_BAD_MESSAGE: return "bad message type";
    case EDZ_STATUS_BAD_DIMENSIONS: return "bad dimensions or format";
    case EDZ_STATUS_BAD_LENGTH: return "bad payload length";
    case EDZ_STATUS_BAD_CRC: return "bad crc";
    case EDZ_STATUS_ACCELERATOR_TIMEOUT: return "accelerator timeout";
    case EDZ_STATUS_DMA_ERROR: return "dma error";
    default: return "internal error";
    }
}
