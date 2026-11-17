#ifndef EDZ_ACCEL_IO_H
#define EDZ_ACCEL_IO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EDZ_RGB_FRAME_BYTES (320u * 320u * 3u)
#define EDZ_ACCEL_INPUT_WORDS (320u * 320u / 2u)
#define EDZ_ACCEL_INPUT_BYTES (EDZ_ACCEL_INPUT_WORDS * sizeof(uint64_t))

/* Pack two RGB888 pixels into TDATA[47:0]; TDATA[63:48] is zero padding. */
int edz_pack_axis_rgb(const uint8_t rgb[EDZ_RGB_FRAME_BYTES], size_t rgb_length,
                      uint64_t packed[EDZ_ACCEL_INPUT_WORDS]);

#ifdef __cplusplus
}
#endif

#endif
