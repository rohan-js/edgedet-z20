#include "edz_accel_io.h"
#include "edz_postprocess.h"
#include "edz_protocol.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void test_crc(void) {
    static const char input[] = "123456789";
    assert(edz_crc32(input, 9u) == 0xcbf43926u);
}

static void test_axis_rgb_packing(void) {
    static uint8_t rgb[EDZ_RGB_FRAME_BYTES];
    static uint64_t packed[EDZ_ACCEL_INPUT_WORDS];
    rgb[0] = 0x11u; rgb[1] = 0x22u; rgb[2] = 0x33u;
    rgb[3] = 0x44u; rgb[4] = 0x55u; rgb[5] = 0x66u;
    assert(edz_pack_axis_rgb(rgb, sizeof(rgb), packed) == 0);
    assert(packed[0] == UINT64_C(0x0000665544332211));
    assert(edz_pack_axis_rgb(rgb, sizeof(rgb) - 1u, packed) == -1);
}

static void test_request_round_trip(void) {
    edz_request_header_t source = {EDZ_PROTOCOL_VERSION, EDZ_MESSAGE_FRAME, 42u,
                                   UINT64_C(1234567890123), 320u, 320u, 960u,
                                   EDZ_PIXEL_RGB888, 307200u, 0x12345678u};
    edz_request_header_t decoded;
    uint8_t wire[EDZ_REQUEST_HEADER_SIZE];
    assert(edz_encode_request_header(&source, wire) == 0);
    assert(memcmp(wire, EDZ_MAGIC, 4u) == 0);
    assert(edz_decode_request_header(wire, &decoded) == 0);
    assert(decoded.frame_id == source.frame_id);
    assert(decoded.timestamp_us == source.timestamp_us);
    assert(decoded.payload_length == source.payload_length);
    assert(decoded.crc32 == source.crc32);
    assert(edz_validate_request(&decoded) == EDZ_STATUS_OK);
    decoded.stride = 959u;
    assert(edz_validate_request(&decoded) == EDZ_STATUS_BAD_DIMENSIONS);
}

static void test_response_and_detection_round_trip(void) {
    edz_response_header_t source = {EDZ_PROTOCOL_VERSION, EDZ_STATUS_OK, 99u,
                                    UINT64_C(1000), UINT64_C(1200), 1u, 0u,
                                    3u, EDZ_DETECTION_WIRE_SIZE, 0xabcdef01u};
    edz_response_header_t decoded;
    edz_detection_t d = {3u, 7u, 0.75f, 0.1f, 0.2f, 0.8f, 0.9f};
    edz_detection_t d2;
    uint8_t header_wire[EDZ_RESPONSE_HEADER_SIZE];
    uint8_t detection_wire[EDZ_DETECTION_WIRE_SIZE];
    assert(edz_encode_response_header(&source, header_wire) == 0);
    assert(edz_decode_response_header(header_wire, &decoded) == 0);
    assert(decoded.total_cycles == source.total_cycles);
    assert(decoded.dropped_frames == source.dropped_frames);
    assert(edz_encode_detection(&d, detection_wire) == 0);
    assert(edz_decode_detection(detection_wire, &d2) == 0);
    assert(d2.class_id == 3u && d2.flags == 7u);
    assert(fabsf(d2.score - 0.75f) < 1e-6f);
    assert(fabsf(d2.x2 - 0.8f) < 1e-6f);
}

static void test_crc_covers_header_and_payload(void) {
    uint8_t payload[3] = {1u, 2u, 3u};
    uint8_t wire[EDZ_REQUEST_HEADER_SIZE];
    edz_request_header_t header = {EDZ_PROTOCOL_VERSION, EDZ_MESSAGE_FRAME, 1u,
                                   2u, 320u, 320u, 960u, EDZ_PIXEL_RGB888,
                                   sizeof(payload), 0u};
    uint32_t first;
    uint32_t second;
    edz_encode_request_header(&header, wire);
    first = edz_request_crc(wire, payload, sizeof(payload));
    payload[2] ^= 1u;
    second = edz_request_crc(wire, payload, sizeof(payload));
    assert(first != second);
}

static void test_decode_and_nms(void) {
    int16_t tensor[EDZ_HEAD_VALUE_COUNT];
    edz_detection_t output[EDZ_MAX_DETECTIONS];
    edz_decode_config_t config = edz_default_decode_config();
    size_t cell;
    size_t count;
    for (cell = 0u; cell < EDZ_HEAD_VALUE_COUNT / EDZ_HEAD_CHANNELS; ++cell) {
        size_t channel;
        for (channel = 0u; channel < 7u; ++channel)
            tensor[cell * EDZ_HEAD_CHANNELS + channel] = -32768;
        for (channel = 7u; channel < EDZ_HEAD_CHANNELS; ++channel)
            tensor[cell * EDZ_HEAD_CHANNELS + channel] = 0;
    }
    /* Grid cell (10,10), class car, high centerness, one-cell box distances. */
    cell = 10u * 20u + 10u;
    tensor[cell * EDZ_HEAD_CHANNELS + 3u] = 2048;
    tensor[cell * EDZ_HEAD_CHANNELS + 6u] = 2048;
    tensor[cell * EDZ_HEAD_CHANNELS + 7u] = 256;
    tensor[cell * EDZ_HEAD_CHANNELS + 8u] = 256;
    tensor[cell * EDZ_HEAD_CHANNELS + 9u] = 256;
    tensor[cell * EDZ_HEAD_CHANNELS + 10u] = 256;
    count = edz_decode_and_nms(tensor, &config, output);
    assert(count == 1u);
    assert(output[0].class_id == 3u);
    assert(output[0].score > 0.99f);
    assert(output[0].x1 < output[0].x2);
}

int main(void) {
    test_axis_rgb_packing();
    test_crc();
    test_request_round_trip();
    test_response_and_detection_round_trip();
    test_crc_covers_header_and_payload();
    test_decode_and_nms();
    puts("edz runtime tests passed");
    return 0;
}
