/*
 * maxpool.cpp
 * 2×2 MaxPool Layer
 * 
 * Downsamples spatial dimensions by 2× in each direction.
 * Selects the maximum value in each 2×2 window.
 */

#include "cnn_types.h"

// ============================================================
// MaxPool 2×2 for Conv1 output: 16×30×30 → 16×15×15
// ============================================================
void maxpool_layer1(
    data_t input[CONV1_OUT_CH][CONV1_OUT_H][CONV1_OUT_W],
    data_t output[CONV1_OUT_CH][POOL1_OUT_H][POOL1_OUT_W])
{
    CH_LOOP:
    for (int c = 0; c < CONV1_OUT_CH; c++) {
        H_LOOP:
        for (int h = 0; h < POOL1_OUT_H; h++) {
            W_LOOP:
            for (int w = 0; w < POOL1_OUT_W; w++) {
                #pragma HLS PIPELINE II=1

                data_t val0 = input[c][2 * h    ][2 * w    ];
                data_t val1 = input[c][2 * h    ][2 * w + 1];
                data_t val2 = input[c][2 * h + 1][2 * w    ];
                data_t val3 = input[c][2 * h + 1][2 * w + 1];

                data_t max01 = (val0 > val1) ? val0 : val1;
                data_t max23 = (val2 > val3) ? val2 : val3;
                output[c][h][w] = (max01 > max23) ? max01 : max23;
            }
        }
    }
}

// ============================================================
// MaxPool 2×2 for Conv2 output: 32×13×13 → 32×6×6
// Note: 13 is odd, so we pool only the first 12 rows/cols
// ============================================================
void maxpool_layer2(
    data_t input[CONV2_OUT_CH][CONV2_OUT_H][CONV2_OUT_W],
    data_t output[CONV2_OUT_CH][POOL2_OUT_H][POOL2_OUT_W])
{
    CH_LOOP2:
    for (int c = 0; c < CONV2_OUT_CH; c++) {
        H_LOOP2:
        for (int h = 0; h < POOL2_OUT_H; h++) {
            W_LOOP2:
            for (int w = 0; w < POOL2_OUT_W; w++) {
                #pragma HLS PIPELINE II=1

                data_t val0 = input[c][2 * h    ][2 * w    ];
                data_t val1 = input[c][2 * h    ][2 * w + 1];
                data_t val2 = input[c][2 * h + 1][2 * w    ];
                data_t val3 = input[c][2 * h + 1][2 * w + 1];

                data_t max01 = (val0 > val1) ? val0 : val1;
                data_t max23 = (val2 > val3) ? val2 : val3;
                output[c][h][w] = (max01 > max23) ? max01 : max23;
            }
        }
    }
}
