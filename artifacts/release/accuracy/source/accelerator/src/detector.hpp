#ifndef EDGEDET_DETECTOR_HPP
#define EDGEDET_DETECTOR_HPP

#include "edgedet_types.hpp"

namespace edgedet {

void detector_scaffold(hls::stream<QuantizedRgb> &pixels,
                       hls::stream<output_t> &predictions,
                       ap_uint<32> &saturation_count,
                       ap_uint<64> &work_count);

void pack_predictions(hls::stream<output_t> &predictions,
                      hls::stream<axis64_t> &output,
                      ap_uint<32> &word_count,
                      ap_uint<64> &work_count);

}  // namespace edgedet

#endif
