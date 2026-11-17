#ifndef EDGEDET_DETECTOR_FULL_HPP
#define EDGEDET_DETECTOR_FULL_HPP

#include "edgedet_types.hpp"

namespace edgedet {

void detector_full_network(hls::stream<QuantizedRgb> &pixels,
                           hls::stream<output_t> &predictions,
                           ap_uint<32> &saturation_count,
                           ap_uint<64> &work_count);

}  // namespace edgedet

#endif
