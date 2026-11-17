#include "edz_accel_io.h"

int edz_pack_axis_rgb(const uint8_t rgb[EDZ_RGB_FRAME_BYTES], size_t rgb_length,
                      uint64_t packed[EDZ_ACCEL_INPUT_WORDS]) {
    size_t word;
    if (!rgb || !packed || rgb_length != EDZ_RGB_FRAME_BYTES) return -1;
    for (word = 0u; word < EDZ_ACCEL_INPUT_WORDS; ++word) {
        const uint8_t *pixel = rgb + word * 6u;
        packed[word] = (uint64_t)pixel[0] |
                       ((uint64_t)pixel[1] << 8) |
                       ((uint64_t)pixel[2] << 16) |
                       ((uint64_t)pixel[3] << 24) |
                       ((uint64_t)pixel[4] << 32) |
                       ((uint64_t)pixel[5] << 40);
    }
    return 0;
}
