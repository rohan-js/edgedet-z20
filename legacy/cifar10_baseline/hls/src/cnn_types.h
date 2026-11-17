/*
 * cnn_types.h
 * Common type definitions and constants for CNN accelerator
 * 
 * Uses ap_fixed for resource-efficient fixed-point arithmetic.
 * 16-bit fixed point uses ~4x fewer resources than 32-bit float.
 */

#ifndef CNN_TYPES_H
#define CNN_TYPES_H

#include <ap_fixed.h>
#include <hls_stream.h>
#include <ap_int.h>

// ============================================================
// Fixed-Point Data Types
// ============================================================
// ap_fixed<total_bits, integer_bits>
// - data_t:   16-bit, 6 integer bits → range [-32, 32), precision 2^-10
// - weight_t: 16-bit, 6 integer bits → same as data
// - acc_t:    32-bit, 16 integer bits → wide accumulator to prevent overflow

typedef ap_fixed<16, 6>  data_t;    // Activations / input data
typedef ap_fixed<16, 6>  weight_t;  // Network weights
typedef ap_fixed<32, 16> acc_t;     // Accumulator (wider to prevent overflow)

// ============================================================
// Network Architecture Constants
// ============================================================
// Simple CNN for image classification:
//   Input(3×32×32) → Conv1(16×30×30) → Pool1(16×15×15)
//                   → Conv2(32×13×13) → Pool2(32×6×6)
//                   → FC(NUM_CLASSES)

// Input dimensions
#define IMG_CH    3       // RGB channels
#define IMG_H     32      // Input height (resized)
#define IMG_W     32      // Input width (resized)

// Conv Layer 1 parameters
#define CONV1_IN_CH   3
#define CONV1_OUT_CH  16
#define CONV1_K       3   // 3x3 kernel
#define CONV1_OUT_H   (IMG_H - CONV1_K + 1)   // 30
#define CONV1_OUT_W   (IMG_W - CONV1_K + 1)    // 30

// Pool Layer 1 parameters
#define POOL1_OUT_H   (CONV1_OUT_H / 2)   // 15
#define POOL1_OUT_W   (CONV1_OUT_W / 2)    // 15

// Conv Layer 2 parameters
#define CONV2_IN_CH   16
#define CONV2_OUT_CH  32
#define CONV2_K       3   // 3x3 kernel
#define CONV2_OUT_H   (POOL1_OUT_H - CONV2_K + 1)  // 13
#define CONV2_OUT_W   (POOL1_OUT_W - CONV2_K + 1)   // 13

// Pool Layer 2 parameters
#define POOL2_OUT_H   (CONV2_OUT_H / 2)   // 6
#define POOL2_OUT_W   (CONV2_OUT_W / 2)    // 6

// Fully Connected layer
#define FC_INPUT_SIZE (CONV2_OUT_CH * POOL2_OUT_H * POOL2_OUT_W)  // 32*6*6 = 1152
#define NUM_CLASSES   10  // e.g., 10 object classes

// ============================================================
// AXI Interface Data Width
// ============================================================
#define AXI_DATA_WIDTH 32

#endif // CNN_TYPES_H
