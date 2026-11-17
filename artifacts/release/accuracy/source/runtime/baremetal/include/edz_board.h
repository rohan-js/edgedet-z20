#ifndef EDZ_BOARD_H
#define EDZ_BOARD_H

#include <stddef.h>
#include <stdint.h>

#define EDZ_INPUT_BUFFER_ADDRESS UINT32_C(0x10000000)
#define EDZ_OUTPUT_BUFFER_ADDRESS UINT32_C(0x10100000)
#define EDZ_ACCELERATOR_ADDRESS UINT32_C(0x43c00000)
#define EDZ_DMA_ADDRESS UINT32_C(0x40400000)
#define EDZ_ACCELERATOR_OUTPUT_BYTES (5500u * sizeof(int16_t))

typedef struct {
    uint64_t kernel_cycles;
    uint64_t total_cycles;
} edz_board_stats_t;

int edz_board_init(void);
int edz_board_infer(const uint8_t *rgb, size_t rgb_length,
                    int16_t output[5500], uint32_t timeout_ms,
                    edz_board_stats_t *stats);
void edz_board_recover(void);

#endif
