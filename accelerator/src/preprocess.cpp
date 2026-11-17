#include "preprocess.hpp"

#include "model_config.hpp"
#include "quant_conv.hpp"

namespace edgedet {

namespace {

activation_t normalize(ap_uint<8> averaged,
                       int channel,
                       ap_uint<32> &saturations) {
#pragma HLS INLINE
  ap_int<40> scaled = static_cast<ap_int<40> >(averaged) *
                          model::kInputMultiplier[channel] +
                      model::kInputBias[channel];
  const ap_int<40> half = static_cast<ap_int<40> >(1)
                          << (model::kInputRightShift - 1);
  ap_int<40> rounded;
  if (scaled >= 0) {
    rounded = (scaled + half) >> model::kInputRightShift;
  } else {
    ap_int<40> magnitude = -scaled;
    rounded = -((magnitude + half) >> model::kInputRightShift);
  }
  return saturate_int8(rounded, saturations);
}

}  // namespace

void preprocess_320_to_160(hls::stream<axis64_t> &input,
                           hls::stream<QuantizedRgb> &output,
                           ap_uint<32> &status,
                           ap_uint<32> &word_count,
                           ap_uint<32> &saturation_count,
                           ap_uint<64> &work_count) {
  ap_uint<9> previous_horizontal[kNetworkWidth][3];
#pragma HLS ARRAY_PARTITION variable=previous_horizontal complete dim=2
#pragma HLS BIND_STORAGE variable=previous_horizontal type=ram_2p impl=bram

  status = EDZ_MODEL_WEIGHTS_PRESENT ? 0 : kStatusPlaceholderModel;
  word_count = 0;
  saturation_count = 0;
  work_count = 0;

  for (int y = 0; y < kInputHeight; ++y) {
    for (int x_word = 0; x_word < kInputWidth / 2; ++x_word) {
#pragma HLS PIPELINE II=1
      axis64_t word = input.read();
      ++word_count;
      ++work_count;

      if (word.keep != 0xFF) status |= kStatusBadKeep;
      if (word.strb != 0xFF) status |= kStatusBadStrb;
      const bool expected_last = (word_count == kInputWords);
      if (word.last && !expected_last) status |= kStatusEarlyTlast;
      if (!word.last && expected_last) status |= kStatusMissingTlast;

      ap_uint<8> p0[3];
      ap_uint<8> p1[3];
#pragma HLS ARRAY_PARTITION variable=p0 complete
#pragma HLS ARRAY_PARTITION variable=p1 complete
      p0[0] = word.data.range(7, 0);
      p0[1] = word.data.range(15, 8);
      p0[2] = word.data.range(23, 16);
      p1[0] = word.data.range(31, 24);
      p1[1] = word.data.range(39, 32);
      p1[2] = word.data.range(47, 40);

      QuantizedRgb quantized;
      for (int channel = 0; channel < 3; ++channel) {
#pragma HLS UNROLL
        ap_uint<9> horizontal = p0[channel] + p1[channel];
        if ((y & 1) == 0) {
          previous_horizontal[x_word][channel] = horizontal;
        } else {
          ap_uint<10> sum4 = previous_horizontal[x_word][channel] + horizontal;
          // Exact integer 2x2 area average, round-to-nearest for non-negative RGB.
          ap_uint<8> average = (sum4 + 2) >> 2;
          activation_t value = normalize(average, channel, saturation_count);
          if (channel == 0) quantized.r = value;
          if (channel == 1) quantized.g = value;
          if (channel == 2) quantized.b = value;
        }
      }
      if ((y & 1) != 0) output.write(quantized);
    }
  }
}

}  // namespace edgedet
