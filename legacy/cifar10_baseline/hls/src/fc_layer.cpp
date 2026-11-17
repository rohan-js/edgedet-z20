/*
 * fc_layer.cpp
 * Fully Connected (Dense) Layer
 * 
 * OPTIMIZED for ZedBoard xc7z020:
 *   - Pipeline on inner dot-product loop (1 MAC/clock)
 *   - Sequential class processing (no parallel unrolling)
 *   - ~3 DSPs instead of 34, ~2K FF instead of 197K
 */

#include "cnn_types.h"

// ============================================================
// Fully Connected Layer: 1152 → NUM_CLASSES
// ============================================================
void fc_layer(
    data_t   input[CONV2_OUT_CH][POOL2_OUT_H][POOL2_OUT_W],
    weight_t weights[NUM_CLASSES][FC_INPUT_SIZE],
    weight_t bias[NUM_CLASSES],
    data_t   output[NUM_CLASSES])
{
    CLASS_LOOP:
    for (int cls = 0; cls < NUM_CLASSES; cls++) {

        acc_t sum = (acc_t)bias[cls];
        int idx = 0;

        // Flatten and multiply — pipeline the inner loop
        FC_CH:
        for (int c = 0; c < CONV2_OUT_CH; c++) {
            FC_H:
            for (int h = 0; h < POOL2_OUT_H; h++) {
                FC_W:
                for (int w = 0; w < POOL2_OUT_W; w++) {
                    #pragma HLS PIPELINE II=1
                    sum += (acc_t)input[c][h][w] * (acc_t)weights[cls][idx];
                    idx++;
                }
            }
        }

        output[cls] = (data_t)sum;
    }
}

// ============================================================
// Argmax (for classification)
// ============================================================
void argmax(
    data_t input[NUM_CLASSES],
    int   *predicted_class,
    data_t *confidence)
{
    #pragma HLS INLINE

    data_t max_val = input[0];
    int    max_idx = 0;

    ARGMAX_LOOP:
    for (int i = 1; i < NUM_CLASSES; i++) {
        #pragma HLS PIPELINE II=1
        if (input[i] > max_val) {
            max_val = input[i];
            max_idx = i;
        }
    }

    *predicted_class = max_idx;
    *confidence = max_val;
}
