#ifndef EDZ_PROTOCOL_H
#define EDZ_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EDZ_MAGIC "EDZ2"
#define EDZ_PROTOCOL_VERSION 1u
#define EDZ_REQUEST_HEADER_SIZE 36u
#define EDZ_RESPONSE_HEADER_SIZE 44u
#define EDZ_DETECTION_WIRE_SIZE 24u
#define EDZ_MAX_FRAME_PAYLOAD (320u * 320u * 3u)
#define EDZ_MAX_DETECTIONS 100u

typedef enum {
    EDZ_MESSAGE_FRAME = 1,
    EDZ_MESSAGE_DETECTIONS = 2
} edz_message_type_t;

typedef enum {
    EDZ_PIXEL_RGB888 = 1
} edz_pixel_format_t;

typedef enum {
    EDZ_STATUS_OK = 0,
    EDZ_STATUS_BAD_MAGIC = 1,
    EDZ_STATUS_BAD_VERSION = 2,
    EDZ_STATUS_BAD_MESSAGE = 3,
    EDZ_STATUS_BAD_DIMENSIONS = 4,
    EDZ_STATUS_BAD_LENGTH = 5,
    EDZ_STATUS_BAD_CRC = 6,
    EDZ_STATUS_ACCELERATOR_TIMEOUT = 7,
    EDZ_STATUS_DMA_ERROR = 8,
    EDZ_STATUS_INTERNAL_ERROR = 9
} edz_status_t;

typedef struct {
    uint16_t version;
    uint16_t message_type;
    uint32_t frame_id;
    uint64_t timestamp_us;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint16_t pixel_format;
    uint32_t payload_length;
    uint32_t crc32;
} edz_request_header_t;

typedef struct {
    uint16_t version;
    uint16_t status;
    uint32_t frame_id;
    uint64_t kernel_cycles;
    uint64_t total_cycles;
    uint16_t detection_count;
    uint16_t reserved;
    uint32_t dropped_frames;
    uint32_t payload_length;
    uint32_t crc32;
} edz_response_header_t;

typedef struct {
    uint16_t class_id;
    uint16_t flags;
    float score;
    float x1;
    float y1;
    float x2;
    float y2;
} edz_detection_t;

uint32_t edz_crc32_init(void);
uint32_t edz_crc32_update(uint32_t state, const void *data, size_t length);
uint32_t edz_crc32_finish(uint32_t state);
uint32_t edz_crc32(const void *data, size_t length);

int edz_encode_request_header(const edz_request_header_t *header,
                              uint8_t out[EDZ_REQUEST_HEADER_SIZE]);
int edz_decode_request_header(const uint8_t in[EDZ_REQUEST_HEADER_SIZE],
                              edz_request_header_t *header);
int edz_encode_response_header(const edz_response_header_t *header,
                               uint8_t out[EDZ_RESPONSE_HEADER_SIZE]);
int edz_decode_response_header(const uint8_t in[EDZ_RESPONSE_HEADER_SIZE],
                               edz_response_header_t *header);
int edz_encode_detection(const edz_detection_t *detection,
                         uint8_t out[EDZ_DETECTION_WIRE_SIZE]);
int edz_decode_detection(const uint8_t in[EDZ_DETECTION_WIRE_SIZE],
                         edz_detection_t *detection);

/* CRC covers the encoded header excluding its final CRC field, then payload. */
uint32_t edz_request_crc(const uint8_t encoded_header[EDZ_REQUEST_HEADER_SIZE],
                         const void *payload, size_t payload_length);
uint32_t edz_response_crc(const uint8_t encoded_header[EDZ_RESPONSE_HEADER_SIZE],
                          const void *payload, size_t payload_length);

edz_status_t edz_validate_request(const edz_request_header_t *header);
const char *edz_status_string(edz_status_t status);

#ifdef __cplusplus
}
#endif

#endif
