/*
 * conv2d.cpp
 * 2D Convolution Layer with fused ReLU activation
 * 
 * OPTIMIZED for ZedBoard xc7z020:
 *   - Sequential accumulation (no UNROLL) to minimize DSP/FF/LUT
 *   - Pipeline on innermost kernel loop for reasonable throughput
 *   - No array partitioning needed
 */

#include "cnn_types.h"

// ============================================================
// Conv2D Layer 1: 3×32×32 → 16×30×30 (with ReLU)
// ============================================================
void conv2d_layer1(
    data_t   input[CONV1_IN_CH][IMG_H][IMG_W],
    weight_t weights[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K],
    weight_t bias[CONV1_OUT_CH],
    data_t   output[CONV1_OUT_CH][CONV1_OUT_H][CONV1_OUT_W])
{
    OC_LOOP:
    for (int oc = 0; oc < CONV1_OUT_CH; oc++) {
        OH_LOOP:
        for (int oh = 0; oh < CONV1_OUT_H; oh++) {
            OW_LOOP:
            for (int ow = 0; ow < CONV1_OUT_W; ow++) {

                acc_t sum = (acc_t)bias[oc];

                IC_LOOP:
                for (int ic = 0; ic < CONV1_IN_CH; ic++) {
                    KH_LOOP:
                    for (int kh = 0; kh < CONV1_K; kh++) {
                        KW_LOOP:
                        for (int kw = 0; kw < CONV1_K; kw++) {
                            #pragma HLS PIPELINE II=1
                            sum += (acc_t)input[ic][oh + kh][ow + kw]
                                 * (acc_t)weights[oc][ic][kh][kw];
                        }
                    }
                }

                // Fused ReLU activation
                output[oc][oh][ow] = (sum > 0) ? (data_t)sum : (data_t)0;
            }
        }
    }
}

// ============================================================
// Conv2D Layer 2: 16×15×15 → 32×13×13 (with ReLU)
// ============================================================
void conv2d_layer2(
    data_t   input[CONV2_IN_CH][POOL1_OUT_H][POOL1_OUT_W],
    weight_t weights[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K],
    weight_t bias[CONV2_OUT_CH],
    data_t   output[CONV2_OUT_CH][CONV2_OUT_H][CONV2_OUT_W])
{
    OC_LOOP2:
    for (int oc = 0; oc < CONV2_OUT_CH; oc++) {
        OH_LOOP2:
        for (int oh = 0; oh < CONV2_OUT_H; oh++) {
            OW_LOOP2:
            for (int ow = 0; ow < CONV2_OUT_W; ow++) {

                acc_t sum = (acc_t)bias[oc];

                IC_LOOP2:
                for (int ic = 0; ic < CONV2_IN_CH; ic++) {
                    KH_LOOP2:
                    for (int kh = 0; kh < CONV2_K; kh++) {
                        KW_LOOP2:
                        for (int kw = 0; kw < CONV2_K; kw++) {
                            #pragma HLS PIPELINE II=1
                            sum += (acc_t)input[ic][oh + kh][ow + kw]
                                 * (acc_t)weights[oc][ic][kh][kw];
                        }
                    }
                }

                // Fused ReLU activation
                output[oc][oh][ow] = (sum > 0) ? (data_t)sum : (data_t)0;
            }
        }
    }
}
