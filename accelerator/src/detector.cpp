#include "detector.hpp"

#include "detector_full.hpp"
#include "model_config.hpp"
#include "quant_conv.hpp"

namespace edgedet {

namespace {

output_t placeholder_projection(ap_int<24> sums[3],
                                int samples,
                                int field,
                                int grid_size,
                                ap_uint<32> &saturations) {
#pragma HLS INLINE
  if (field >= kLeft) {
    // Positive Q8 box-distance placeholder. A trained package replaces this.
    const int distance_cells = (grid_size == kFineGrid) ? 4 : 2;
    return static_cast<output_t>(distance_cells << model::kOutputFractionBits);
  }

  activation_t means[3];
  weight8_t weights[3];
#pragma HLS ARRAY_PARTITION variable=means complete
#pragma HLS ARRAY_PARTITION variable=weights complete
  for (int channel = 0; channel < 3; ++channel) {
#pragma HLS UNROLL
    means[channel] = static_cast<activation_t>(sums[channel] / samples);
    weights[channel] = model::kPlaceholderHeadWeights[field][channel];
  }
  accumulator_t value =
      quantized_dot<3>(means, weights, model::kPlaceholderHeadBias[field]);
  return saturate_int16(value, saturations);
}

template <int GridSize, int CellPixels>
void emit_grid(ap_int<24> sums[GridSize * GridSize][3],
               hls::stream<output_t> &predictions,
               ap_uint<32> &saturations,
               ap_uint<64> &work_count) {
  for (int cell = 0; cell < GridSize * GridSize; ++cell) {
    for (int field_base = 0; field_base < kFieldsPerCell;
         field_base += model::kPe) {
#pragma HLS PIPELINE II=1
      for (int lane = 0; lane < model::kPe; ++lane) {
#pragma HLS UNROLL
        const int field = field_base + lane;
        if (field < kFieldsPerCell) {
          predictions.write(placeholder_projection(
              sums[cell], CellPixels, field, GridSize, saturations));
        }
      }
    }
  }
  work_count += GridSize * GridSize * kFieldsPerCell;
}

}  // namespace

void detector_placeholder(hls::stream<QuantizedRgb> &pixels,
                          hls::stream<output_t> &predictions,
                          ap_uint<32> &saturation_count,
                          ap_uint<64> &work_count) {
  ap_int<24> fine_sums[kFineGrid * kFineGrid][3];
  ap_int<24> coarse_sums[kCoarseGrid * kCoarseGrid][3];
#pragma HLS ARRAY_PARTITION variable=fine_sums complete dim=2
#pragma HLS ARRAY_PARTITION variable=coarse_sums complete dim=2
#pragma HLS BIND_STORAGE variable=fine_sums type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=coarse_sums type=ram_2p impl=bram

  saturation_count = 0;
  work_count = 0;

  for (int cell = 0; cell < kFineGrid * kFineGrid; ++cell) {
#pragma HLS PIPELINE II=1
    for (int channel = 0; channel < 3; ++channel) {
#pragma HLS UNROLL
      fine_sums[cell][channel] = 0;
    }
  }
  for (int cell = 0; cell < kCoarseGrid * kCoarseGrid; ++cell) {
#pragma HLS PIPELINE II=1
    for (int channel = 0; channel < 3; ++channel) {
#pragma HLS UNROLL
      coarse_sums[cell][channel] = 0;
    }
  }

  for (int y = 0; y < kNetworkHeight; ++y) {
    for (int x = 0; x < kNetworkWidth; ++x) {
#pragma HLS PIPELINE II=1
      QuantizedRgb pixel = pixels.read();
      const int fine_cell = (y >> 3) * kFineGrid + (x >> 3);
      const int coarse_cell = (y >> 4) * kCoarseGrid + (x >> 4);
      fine_sums[fine_cell][0] += pixel.r;
      fine_sums[fine_cell][1] += pixel.g;
      fine_sums[fine_cell][2] += pixel.b;
      coarse_sums[coarse_cell][0] += pixel.r;
      coarse_sums[coarse_cell][1] += pixel.g;
      coarse_sums[coarse_cell][2] += pixel.b;
      ++work_count;
    }
  }

  emit_grid<kFineGrid, 64>(fine_sums, predictions, saturation_count, work_count);
  emit_grid<kCoarseGrid, 256>(coarse_sums, predictions, saturation_count,
                              work_count);
}

void detector_scaffold(hls::stream<QuantizedRgb> &pixels,
                       hls::stream<output_t> &predictions,
                       ap_uint<32> &saturation_count,
                       ap_uint<64> &work_count) {
#if EDZ_MODEL_WEIGHTS_PRESENT
  detector_full_network(pixels, predictions, saturation_count, work_count);
#else
  detector_placeholder(pixels, predictions, saturation_count, work_count);
#endif
}

void pack_predictions(hls::stream<output_t> &predictions,
                      hls::stream<axis64_t> &output,
                      ap_uint<32> &word_count,
                      ap_uint<64> &work_count) {
  word_count = 0;
  work_count = 0;
  for (int word_index = 0; word_index < kOutputWords; ++word_index) {
#pragma HLS PIPELINE II=1
    axis64_t word;
    word.data = 0;
    for (int lane = 0; lane < kValuesPerOutputWord; ++lane) {
#pragma HLS UNROLL
      output_t value = predictions.read();
      word.data.range(16 * lane + 15, 16 * lane) =
          static_cast<ap_uint<16> >(value);
    }
    word.keep = 0xFF;
    word.strb = 0xFF;
    word.last = (word_index == kOutputWords - 1);
    output.write(word);
    ++word_count;
    ++work_count;
  }
}

}  // namespace edgedet
