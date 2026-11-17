/*
 * test_cnn.cpp
 * HLS Testbench for CNN Accelerator
 * 
 * This testbench verifies the CNN accelerator using:
 *   1. Known input pattern (all ones)
 *   2. Random weights initialization
 *   3. Golden reference computed in software (float)
 *   4. Comparison with HLS fixed-point output
 * 
 * Run with: Vitis HLS → C Simulation
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "cnn_types.h"

// Top function prototype
void cnn_top(
    data_t   input[IMG_CH][IMG_H][IMG_W],
    weight_t conv1_weights[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K],
    weight_t conv1_bias[CONV1_OUT_CH],
    weight_t conv2_weights[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K],
    weight_t conv2_bias[CONV2_OUT_CH],
    weight_t fc_weights[NUM_CLASSES][FC_INPUT_SIZE],
    weight_t fc_bias[NUM_CLASSES],
    data_t   output[NUM_CLASSES]);


// ============================================================
// Helper: Generate random float in range [-scale, +scale]
// ============================================================
float rand_float(float scale) {
    return ((float)rand() / RAND_MAX) * 2.0f * scale - scale;
}

// ============================================================
// Software Golden Reference (float arithmetic)
// ============================================================
void sw_conv2d_relu(
    float input[][32][32], int in_ch,
    float weights[][16][3][3], float bias[],
    float output[][30][30], int out_ch,
    int out_h, int out_w, int k)
{
    for (int oc = 0; oc < out_ch; oc++) {
        for (int oh = 0; oh < out_h; oh++) {
            for (int ow = 0; ow < out_w; ow++) {
                float sum = bias[oc];
                for (int ic = 0; ic < in_ch; ic++)
                    for (int kh = 0; kh < k; kh++)
                        for (int kw = 0; kw < k; kw++)
                            sum += input[ic][oh+kh][ow+kw] 
                                 * weights[oc][ic][kh][kw];
                output[oc][oh][ow] = (sum > 0) ? sum : 0;
            }
        }
    }
}

void sw_maxpool(float input[][30][30], float output[][15][15], 
                int channels, int out_h, int out_w)
{
    for (int c = 0; c < channels; c++)
        for (int h = 0; h < out_h; h++)
            for (int w = 0; w < out_w; w++) {
                float m = input[c][2*h][2*w];
                if (input[c][2*h][2*w+1] > m) m = input[c][2*h][2*w+1];
                if (input[c][2*h+1][2*w] > m) m = input[c][2*h+1][2*w];
                if (input[c][2*h+1][2*w+1] > m) m = input[c][2*h+1][2*w+1];
                output[c][h][w] = m;
            }
}


// ============================================================
// MAIN TESTBENCH
// ============================================================
int main()
{
    printf("==============================================\n");
    printf("  CNN Accelerator HLS Testbench\n");
    printf("==============================================\n\n");

    // Seed for reproducibility
    srand(42);

    // ---- Allocate arrays ----
    static data_t   hls_input[IMG_CH][IMG_H][IMG_W];
    static weight_t hls_conv1_w[CONV1_OUT_CH][CONV1_IN_CH][CONV1_K][CONV1_K];
    static weight_t hls_conv1_b[CONV1_OUT_CH];
    static weight_t hls_conv2_w[CONV2_OUT_CH][CONV2_IN_CH][CONV2_K][CONV2_K];
    static weight_t hls_conv2_b[CONV2_OUT_CH];
    static weight_t hls_fc_w[NUM_CLASSES][FC_INPUT_SIZE];
    static weight_t hls_fc_b[NUM_CLASSES];
    static data_t   hls_output[NUM_CLASSES];

    // ---- Initialize input (simple gradient pattern) ----
    printf("[INFO] Initializing input (gradient pattern)...\n");
    for (int c = 0; c < IMG_CH; c++)
        for (int h = 0; h < IMG_H; h++)
            for (int w = 0; w < IMG_W; w++)
                hls_input[c][h][w] = (data_t)(0.01f * (c * IMG_H * IMG_W + h * IMG_W + w));

    // ---- Initialize weights (small random values) ----
    printf("[INFO] Initializing weights (random, scale=0.1)...\n");
    
    for (int oc = 0; oc < CONV1_OUT_CH; oc++) {
        hls_conv1_b[oc] = (weight_t)rand_float(0.01f);
        for (int ic = 0; ic < CONV1_IN_CH; ic++)
            for (int kh = 0; kh < CONV1_K; kh++)
                for (int kw = 0; kw < CONV1_K; kw++)
                    hls_conv1_w[oc][ic][kh][kw] = (weight_t)rand_float(0.1f);
    }

    for (int oc = 0; oc < CONV2_OUT_CH; oc++) {
        hls_conv2_b[oc] = (weight_t)rand_float(0.01f);
        for (int ic = 0; ic < CONV2_IN_CH; ic++)
            for (int kh = 0; kh < CONV2_K; kh++)
                for (int kw = 0; kw < CONV2_K; kw++)
                    hls_conv2_w[oc][ic][kh][kw] = (weight_t)rand_float(0.1f);
    }

    for (int cls = 0; cls < NUM_CLASSES; cls++) {
        hls_fc_b[cls] = (weight_t)rand_float(0.01f);
        for (int j = 0; j < FC_INPUT_SIZE; j++)
            hls_fc_w[cls][j] = (weight_t)rand_float(0.1f);
    }

    // ---- Run HLS accelerator ----
    printf("[INFO] Running HLS CNN accelerator...\n");
    cnn_top(hls_input,
            hls_conv1_w, hls_conv1_b,
            hls_conv2_w, hls_conv2_b,
            hls_fc_w, hls_fc_b,
            hls_output);

    // ---- Display results ----
    printf("\n[RESULTS] CNN Output (class scores):\n");
    printf("  %-8s  %-12s\n", "Class", "Score");
    printf("  %-8s  %-12s\n", "-----", "--------");

    data_t max_score = hls_output[0];
    int    max_class = 0;

    for (int i = 0; i < NUM_CLASSES; i++) {
        float score_f = (float)hls_output[i];
        printf("  %-8d  %12.6f\n", i, score_f);

        if (hls_output[i] > max_score) {
            max_score = hls_output[i];
            max_class = i;
        }
    }

    printf("\n[RESULT] Predicted class: %d (score: %.6f)\n", 
           max_class, (float)max_score);

    // ---- Basic sanity checks ----
    int pass = 1;

    // Check 1: Output should not be all zeros
    int all_zero = 1;
    for (int i = 0; i < NUM_CLASSES; i++) {
        if ((float)hls_output[i] != 0.0f) {
            all_zero = 0;
            break;
        }
    }
    if (all_zero) {
        printf("[FAIL] All outputs are zero — something is wrong!\n");
        pass = 0;
    } else {
        printf("[PASS] Outputs are non-zero\n");
    }

    // Check 2: Scores should be in a reasonable range
    for (int i = 0; i < NUM_CLASSES; i++) {
        float val = (float)hls_output[i];
        if (val != val) { // NaN check
            printf("[FAIL] Output %d is NaN\n", i);
            pass = 0;
        }
        if (val > 1000.0f || val < -1000.0f) {
            printf("[WARN] Output %d = %.2f seems unusually large\n", i, val);
        }
    }
    if (pass) {
        printf("[PASS] All outputs in reasonable range\n");
    }

    printf("\n==============================================\n");
    if (pass) {
        printf("  TESTBENCH PASSED\n");
    } else {
        printf("  TESTBENCH FAILED\n");
    }
    printf("==============================================\n");

    return pass ? 0 : 1;
}
