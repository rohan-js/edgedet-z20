/*
 * cnn_top.cpp
 * Top-Level CNN Accelerator Module
 * 
 * OPTIMIZED for ZedBoard xc7z020:
 *   - Removed array partitions (sub-modules process sequentially)
 *   - Single m_axi port for all data (saves logic)
 *   - Kept burst-friendly data loading
 */

#include "cnn_types.h"

// Forward declarations
void conv2d_layer1(
    data_t   input[CONV1_IN_CH][IMG_H][IMG_W],
    weight_t weights[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K],
    weight_t bias[CONV1_OUT_CH],
    data_t   output[CONV1_OUT_CH][CONV1_OUT_H][CONV1_OUT_W]);

void conv2d_layer2(
    data_t   input[CONV2_IN_CH][POOL1_OUT_H][POOL1_OUT_W],
    weight_t weights[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K],
    weight_t bias[CONV2_OUT_CH],
    data_t   output[CONV2_OUT_CH][CONV2_OUT_H][CONV2_OUT_W]);

void maxpool_layer1(
    data_t input[CONV1_OUT_CH][CONV1_OUT_H][CONV1_OUT_W],
    data_t output[CONV1_OUT_CH][POOL1_OUT_H][POOL1_OUT_W]);

void maxpool_layer2(
    data_t input[CONV2_OUT_CH][CONV2_OUT_H][CONV2_OUT_W],
    data_t output[CONV2_OUT_CH][POOL2_OUT_H][POOL2_OUT_W]);

void fc_layer(
    data_t   input[CONV2_OUT_CH][POOL2_OUT_H][POOL2_OUT_W],
    weight_t weights[NUM_CLASSES][FC_INPUT_SIZE],
    weight_t bias[NUM_CLASSES],
    data_t   output[NUM_CLASSES]);


// ============================================================
// TOP-LEVEL CNN ACCELERATOR
// ============================================================
void cnn_top(
    // Input image: 3×32×32
    data_t   input[IMG_CH][IMG_H][IMG_W],

    // Layer 1 weights and bias
    weight_t conv1_weights[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K],
    weight_t conv1_bias[CONV1_OUT_CH],

    // Layer 2 weights and bias
    weight_t conv2_weights[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K],
    weight_t conv2_bias[CONV2_OUT_CH],

    // FC weights and bias
    weight_t fc_weights[NUM_CLASSES][FC_INPUT_SIZE],
    weight_t fc_bias[NUM_CLASSES],

    // Output: class scores
    data_t   output[NUM_CLASSES])
{
    // ========================================================
    // AXI Interface Pragmas
    // ========================================================
    #pragma HLS INTERFACE m_axi port=input         bundle=gmem0 depth=3072
    #pragma HLS INTERFACE m_axi port=conv1_weights bundle=gmem1 depth=432
    #pragma HLS INTERFACE m_axi port=conv1_bias    bundle=gmem1 depth=16
    #pragma HLS INTERFACE m_axi port=conv2_weights bundle=gmem2 depth=4608
    #pragma HLS INTERFACE m_axi port=conv2_bias    bundle=gmem2 depth=32
    #pragma HLS INTERFACE m_axi port=fc_weights    bundle=gmem3 depth=11520
    #pragma HLS INTERFACE m_axi port=fc_bias       bundle=gmem3 depth=10
    #pragma HLS INTERFACE m_axi port=output        bundle=gmem0 depth=10

    #pragma HLS INTERFACE s_axilite port=input
    #pragma HLS INTERFACE s_axilite port=conv1_weights
    #pragma HLS INTERFACE s_axilite port=conv1_bias
    #pragma HLS INTERFACE s_axilite port=conv2_weights
    #pragma HLS INTERFACE s_axilite port=conv2_bias
    #pragma HLS INTERFACE s_axilite port=fc_weights
    #pragma HLS INTERFACE s_axilite port=fc_bias
    #pragma HLS INTERFACE s_axilite port=output
    #pragma HLS INTERFACE s_axilite port=return

    // ========================================================
    // Local buffers (stored in BRAM on FPGA)
    // ========================================================
    // No array partitioning — sequential access is fine for
    // resource-optimized design

    // Input buffer
    data_t local_input[IMG_CH][IMG_H][IMG_W];

    // Intermediate feature maps
    data_t conv1_out[CONV1_OUT_CH][CONV1_OUT_H][CONV1_OUT_W];
    data_t pool1_out[CONV1_OUT_CH][POOL1_OUT_H][POOL1_OUT_W];
    data_t conv2_out[CONV2_OUT_CH][CONV2_OUT_H][CONV2_OUT_W];
    data_t pool2_out[CONV2_OUT_CH][POOL2_OUT_H][POOL2_OUT_W];
    data_t fc_out[NUM_CLASSES];

    // Local weight buffers
    weight_t local_conv1_w[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K];
    weight_t local_conv1_b[CONV1_OUT_CH];
    weight_t local_conv2_w[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K];
    weight_t local_conv2_b[CONV2_OUT_CH];
    weight_t local_fc_w[NUM_CLASSES][FC_INPUT_SIZE];
    weight_t local_fc_b[NUM_CLASSES];

    // ========================================================
    // Step 1: Copy data from DDR to local BRAM
    // ========================================================

    LOAD_INPUT:
    for (int c = 0; c < IMG_CH; c++)
        for (int h = 0; h < IMG_H; h++)
            for (int w = 0; w < IMG_W; w++)
                #pragma HLS PIPELINE II=1
                local_input[c][h][w] = input[c][h][w];

    LOAD_CONV1_W:
    for (int oc = 0; oc < CONV1_OUT_CH; oc++)
        for (int ic = 0; ic < CONV1_IN_CH; ic++)
            for (int kh = 0; kh < CONV1_K; kh++)
                for (int kw = 0; kw < CONV1_K; kw++)
                    #pragma HLS PIPELINE II=1
                    local_conv1_w[oc][ic][kh][kw] = conv1_weights[oc][ic][kh][kw];

    LOAD_CONV1_B:
    for (int i = 0; i < CONV1_OUT_CH; i++)
        #pragma HLS PIPELINE II=1
        local_conv1_b[i] = conv1_bias[i];

    LOAD_CONV2_W:
    for (int oc = 0; oc < CONV2_OUT_CH; oc++)
        for (int ic = 0; ic < CONV2_IN_CH; ic++)
            for (int kh = 0; kh < CONV2_K; kh++)
                for (int kw = 0; kw < CONV2_K; kw++)
                    #pragma HLS PIPELINE II=1
                    local_conv2_w[oc][ic][kh][kw] = conv2_weights[oc][ic][kh][kw];

    LOAD_CONV2_B:
    for (int i = 0; i < CONV2_OUT_CH; i++)
        #pragma HLS PIPELINE II=1
        local_conv2_b[i] = conv2_bias[i];

    LOAD_FC_W:
    for (int cls = 0; cls < NUM_CLASSES; cls++)
        for (int j = 0; j < FC_INPUT_SIZE; j++)
            #pragma HLS PIPELINE II=1
            local_fc_w[cls][j] = fc_weights[cls][j];

    LOAD_FC_B:
    for (int i = 0; i < NUM_CLASSES; i++)
        #pragma HLS PIPELINE II=1
        local_fc_b[i] = fc_bias[i];

    // ========================================================
    // Step 2: Execute CNN Pipeline
    // ========================================================

    // Layer 1: Conv2D (3×32×32 → 16×30×30) + ReLU
    conv2d_layer1(local_input, local_conv1_w, local_conv1_b, conv1_out);

    // Layer 2: MaxPool (16×30×30 → 16×15×15)
    maxpool_layer1(conv1_out, pool1_out);

    // Layer 3: Conv2D (16×15×15 → 32×13×13) + ReLU
    conv2d_layer2(pool1_out, local_conv2_w, local_conv2_b, conv2_out);

    // Layer 4: MaxPool (32×13×13 → 32×6×6)
    maxpool_layer2(conv2_out, pool2_out);

    // Layer 5: Fully Connected (1152 → NUM_CLASSES)
    fc_layer(pool2_out, local_fc_w, local_fc_b, fc_out);

    // ========================================================
    // Step 3: Write results back to DDR
    // ========================================================
    STORE_OUTPUT:
    for (int i = 0; i < NUM_CLASSES; i++) {
        #pragma HLS PIPELINE II=1
        output[i] = fc_out[i];
    }
}
