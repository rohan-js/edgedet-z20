#include "detector_full.hpp"

#include "generated_model.hpp"
#include "model_config.hpp"
#include "quant_conv.hpp"

namespace edgedet {

#if EDZ_MODEL_WEIGHTS_PRESENT
namespace {

enum LayerId {
  kStem = 0,
  kStage1Down = 1,
  kStage1Refine = 2,
  kStage2Down = 3,
  kStage2Refine = 4,
  kStage3Down = 5,
  kStage3Refine = 6,
  kLateral = 7,
  kFineRefine = 8,
  kFineHead = 9,
  kCoarseHead = 10
};

constexpr int kInputElements = kNetworkWidth * kNetworkHeight * 3;
constexpr int kMaxFeatures = 80 * 80 * 16;
constexpr int kFineFeatures = 20 * 20 * 48;

feature_t clamp_relu6(accumulator_t value, int layer, int channel,
                      ap_uint<32> &saturations) {
#pragma HLS INLINE
  if (value < 0) {
    if (value != 0) ++saturations;
    return 0;
  }
  feature_t upper = generated::activation_max(layer, channel);
  if (value > upper) {
    ++saturations;
    return upper;
  }
  return static_cast<feature_t>(value);
}

template <typename InputT, int InputWidth, int InputChannels,
          int OutputChannels, int Kernel, int Stride>
void conv_relu6(const InputT *input, feature_t *output, int layer,
                ap_uint<32> &saturations, ap_uint<64> &work_count) {
#pragma HLS INLINE off
  constexpr int OutputWidth = InputWidth / Stride;
  constexpr int Padding = Kernel / 2;

  for (int oy = 0; oy < OutputWidth; ++oy) {
    for (int ox = 0; ox < OutputWidth; ++ox) {
      for (int oc_base = 0; oc_base < OutputChannels; oc_base += model::kPe) {
        accumulator_t accumulators[model::kPe];
#pragma HLS ARRAY_PARTITION variable=accumulators complete
        for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
          const int oc = oc_base + pe;
          accumulators[pe] =
              (oc < OutputChannels) ? generated::bias(layer, oc) : 0;
        }

        for (int ky = 0; ky < Kernel; ++ky) {
          for (int kx = 0; kx < Kernel; ++kx) {
            for (int ic_base = 0; ic_base < InputChannels;
                 ic_base += model::kSimd) {
#pragma HLS PIPELINE II=1
              for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
                const int oc = oc_base + pe;
                for (int lane = 0; lane < model::kSimd; ++lane) {
#pragma HLS UNROLL
                  const int ic = ic_base + lane;
                  const int iy = oy * Stride + ky - Padding;
                  const int ix = ox * Stride + kx - Padding;
                  if (oc < OutputChannels && ic < InputChannels && iy >= 0 &&
                      iy < InputWidth && ix >= 0 && ix < InputWidth) {
                    const InputT activation =
                        input[(iy * InputWidth + ix) * InputChannels + ic];
                    accumulators[pe] +=
                        static_cast<accumulator_t>(activation) *
                        static_cast<accumulator_t>(
                            generated::weight(layer, oc, ic, ky, kx));
                  }
                }
              }
            }
          }
        }

        for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
          const int oc = oc_base + pe;
          if (oc < OutputChannels) {
            accumulator_t scaled = requantize(
                accumulators[pe], generated::multiplier(layer, oc),
                generated::right_shift(layer, oc));
            output[(oy * OutputWidth + ox) * OutputChannels + oc] =
                clamp_relu6(scaled, layer, oc, saturations);
          }
        }
      }
    }
  }
  work_count += static_cast<ap_uint<64> >(OutputWidth) * OutputWidth *
                OutputChannels * InputChannels * Kernel * Kernel;
}

void upsample_add(feature_t retained[kFineFeatures],
                  const feature_t lateral[10 * 10 * 48],
                  ap_uint<32> &saturations, ap_uint<64> &work_count) {
  for (int y = 0; y < 20; ++y) {
    for (int x = 0; x < 20; ++x) {
      for (int channel = 0; channel < 48; ++channel) {
#pragma HLS PIPELINE II=1
        const int fine_index = (y * 20 + x) * 48 + channel;
        const int lateral_index = ((y >> 1) * 10 + (x >> 1)) * 48 + channel;
        accumulator_t branch0 = requantize(
            retained[fine_index], generated::residual_multiplier(0, channel),
            generated::residual_right_shift(0, channel));
        accumulator_t branch1 = requantize(
            lateral[lateral_index], generated::residual_multiplier(1, channel),
            generated::residual_right_shift(1, channel));
        retained[fine_index] =
            clamp_relu6(branch0 + branch1, kFineRefine, channel, saturations);
        work_count += 2;
      }
    }
  }
}

template <int Width, int InputChannels, int Layer>
void detection_head(const feature_t *input,
                    hls::stream<output_t> &predictions,
                    ap_uint<32> &saturations,
                    ap_uint<64> &work_count) {
  for (int y = 0; y < Width; ++y) {
    for (int x = 0; x < Width; ++x) {
      for (int field_base = 0; field_base < kFieldsPerCell;
           field_base += model::kPe) {
        accumulator_t accumulators[model::kPe];
#pragma HLS ARRAY_PARTITION variable=accumulators complete
        for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
          const int field = field_base + pe;
          accumulators[pe] =
              (field < kFieldsPerCell) ? generated::bias(Layer, field) : 0;
        }
        for (int ic_base = 0; ic_base < InputChannels;
             ic_base += model::kSimd) {
#pragma HLS PIPELINE II=1
          for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
            const int field = field_base + pe;
            for (int lane = 0; lane < model::kSimd; ++lane) {
#pragma HLS UNROLL
              const int ic = ic_base + lane;
              if (field < kFieldsPerCell && ic < InputChannels) {
                feature_t activation =
                    input[(y * Width + x) * InputChannels + ic];
                accumulators[pe] +=
                    static_cast<accumulator_t>(activation) *
                    static_cast<accumulator_t>(
                        generated::weight(Layer, field, ic, 0, 0));
              }
            }
          }
        }
        for (int pe = 0; pe < model::kPe; ++pe) {
#pragma HLS UNROLL
          const int field = field_base + pe;
          if (field < kFieldsPerCell) {
            accumulator_t scaled = requantize(
                accumulators[pe], generated::multiplier(Layer, field),
                generated::right_shift(Layer, field));
            predictions.write(saturate_int16(scaled, saturations));
          }
        }
      }
    }
  }
  work_count += static_cast<ap_uint<64> >(Width) * Width *
                kFieldsPerCell * InputChannels;
}

}  // namespace
#endif

void detector_full_network(hls::stream<QuantizedRgb> &pixels,
                           hls::stream<output_t> &predictions,
                           ap_uint<32> &saturation_count,
                           ap_uint<64> &work_count) {
#if EDZ_MODEL_WEIGHTS_PRESENT
  activation_t input[kInputElements];
  feature_t buffer_a[kMaxFeatures];
  feature_t buffer_b[kMaxFeatures];
  feature_t retained_fine[kFineFeatures];
#pragma HLS BIND_STORAGE variable=input type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=buffer_a type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=buffer_b type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=retained_fine type=ram_2p impl=bram

  saturation_count = 0;
  work_count = 0;
  for (int pixel_index = 0;
       pixel_index < kNetworkWidth * kNetworkHeight; ++pixel_index) {
#pragma HLS PIPELINE II=1
    QuantizedRgb pixel = pixels.read();
    input[pixel_index * 3 + 0] = pixel.r;
    input[pixel_index * 3 + 1] = pixel.g;
    input[pixel_index * 3 + 2] = pixel.b;
  }

  conv_relu6<activation_t, 160, 3, 16, 3, 2>(
      input, buffer_a, kStem, saturation_count, work_count);
  conv_relu6<feature_t, 80, 16, 24, 3, 2>(
      buffer_a, buffer_b, kStage1Down, saturation_count, work_count);
  conv_relu6<feature_t, 40, 24, 24, 3, 1>(
      buffer_b, buffer_a, kStage1Refine, saturation_count, work_count);
  conv_relu6<feature_t, 40, 24, 48, 3, 2>(
      buffer_a, buffer_b, kStage2Down, saturation_count, work_count);
  conv_relu6<feature_t, 20, 48, 48, 3, 1>(
      buffer_b, retained_fine, kStage2Refine, saturation_count, work_count);
  conv_relu6<feature_t, 20, 48, 96, 3, 2>(
      retained_fine, buffer_a, kStage3Down, saturation_count, work_count);
  conv_relu6<feature_t, 10, 96, 96, 3, 1>(
      buffer_a, buffer_b, kStage3Refine, saturation_count, work_count);
  conv_relu6<feature_t, 10, 96, 48, 1, 1>(
      buffer_b, buffer_a, kLateral, saturation_count, work_count);
  upsample_add(retained_fine, buffer_a, saturation_count, work_count);
  conv_relu6<feature_t, 20, 48, 48, 3, 1>(
      retained_fine, buffer_a, kFineRefine, saturation_count, work_count);

  // ABI order is fine grid followed by coarse grid, each cell field-major.
  detection_head<20, 48, kFineHead>(buffer_a, predictions, saturation_count,
                                     work_count);
  detection_head<10, 96, kCoarseHead>(buffer_b, predictions, saturation_count,
                                       work_count);
#else
  (void)pixels;
  (void)predictions;
  saturation_count = 0;
  work_count = 0;
#endif
}

}  // namespace edgedet
