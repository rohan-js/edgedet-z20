#ifndef EDGEDET_QUANT_CONV_HPP
#define EDGEDET_QUANT_CONV_HPP

#include "edgedet_types.hpp"
#include "model_config.hpp"

namespace edgedet {

inline output_t saturate_int16(accumulator_t value, ap_uint<32> &saturations) {
#pragma HLS INLINE
  if (value > 32767) {
    ++saturations;
    return 32767;
  }
  if (value < -32768) {
    ++saturations;
    return -32768;
  }
  return static_cast<output_t>(value);
}

inline activation_t saturate_int8(ap_int<40> value,
                                  ap_uint<32> &saturations) {
#pragma HLS INLINE
  if (value > 127) {
    ++saturations;
    return 127;
  }
  if (value < -128) {
    ++saturations;
    return -128;
  }
  return static_cast<activation_t>(value);
}

// Signed fixed-point requantization with round-to-nearest, ties away from zero.
// multiplier is a generated integer scale and right_shift is non-negative.
inline accumulator_t requantize(accumulator_t value,
                                ap_int<32> multiplier,
                                ap_uint<6> right_shift) {
#pragma HLS INLINE
  ap_int<64> product = static_cast<ap_int<64> >(value) * multiplier;
  if (right_shift == 0) return static_cast<accumulator_t>(product);
  const ap_int<64> half = static_cast<ap_int<64> >(1) << (right_shift - 1);
  if (product >= 0) {
    return static_cast<accumulator_t>((product + half) >> right_shift);
  }
  // Work on magnitude so arithmetic right shift cannot bias exact negative
  // multiples by an extra LSB. This is sign(abs(x)+half)>>shift: nearest with
  // ties away from zero, matching the integer Python/C reference contract.
  ap_int<64> magnitude = -product;
  return static_cast<accumulator_t>(-((magnitude + half) >> right_shift));
}

// Reusable PE/SIMD-oriented dot-product primitive. Generated network code can
// use this for 1x1 and for flattened 3x3 windows. Input channels are padded with
// zeroes to SIMD. PE is expressed by unrolling output-channel blocks at the call
// site; SIMD lanes are unrolled here.
template <int InputChannels>
accumulator_t quantized_dot(const activation_t input[InputChannels],
                            const weight8_t weights[InputChannels],
                            accumulator_t bias) {
#pragma HLS INLINE
  accumulator_t acc = bias;
  for (int base = 0; base < InputChannels; base += model::kSimd) {
#pragma HLS PIPELINE II=1
    accumulator_t lane_sum = 0;
    for (int lane = 0; lane < model::kSimd; ++lane) {
#pragma HLS UNROLL
      const int channel = base + lane;
      if (channel < InputChannels) {
        lane_sum += static_cast<accumulator_t>(input[channel]) *
                    static_cast<accumulator_t>(weights[channel]);
      }
    }
    acc += lane_sum;
  }
  return acc;
}

}  // namespace edgedet

#endif  // EDGEDET_QUANT_CONV_HPP
