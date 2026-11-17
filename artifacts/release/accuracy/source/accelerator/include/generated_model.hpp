#ifndef EDGEDET_GENERATED_MODEL_HPP
#define EDGEDET_GENERATED_MODEL_HPP

#include "edgedet_types.hpp"

// Contract for the model exporter. A release model package supplies a header
// with this exact name earlier on the include path and compiles with
// EDZ_MODEL_WEIGHTS_PRESENT=1. The accessors may unpack W4 or W8 storage, but
// must return sign-extended values and bit-exact integer scaling parameters.
namespace edgedet {
namespace generated {

constexpr unsigned kModelCrc = 0;
constexpr unsigned kConfigHashLow = 0;

inline weight8_t weight(int layer, int output_channel, int input_channel,
                        int kernel_y, int kernel_x) {
  (void)layer;
  (void)output_channel;
  (void)input_channel;
  (void)kernel_y;
  (void)kernel_x;
  return 0;
}

inline accumulator_t bias(int layer, int output_channel) {
  (void)layer;
  (void)output_channel;
  return 0;
}

inline ap_int<32> multiplier(int layer, int output_channel) {
  (void)layer;
  (void)output_channel;
  return 1;
}

inline ap_uint<6> right_shift(int layer, int output_channel) {
  (void)layer;
  (void)output_channel;
  return 0;
}

inline feature_t activation_max(int layer, int output_channel) {
  (void)layer;
  (void)output_channel;
  return 127;
}

// branch 0 is the retained 20x20 stage-2 feature, branch 1 is the upsampled
// lateral feature. Both are converted to the fine-fusion output scale.
inline ap_int<32> residual_multiplier(int branch, int channel) {
  (void)branch;
  (void)channel;
  return 1;
}

inline ap_uint<6> residual_right_shift(int branch, int channel) {
  (void)branch;
  (void)channel;
  return 0;
}

}  // namespace generated
}  // namespace edgedet

#endif
