#ifndef EDGEDET_PREPROCESS_HPP
#define EDGEDET_PREPROCESS_HPP

#include "edgedet_types.hpp"

namespace edgedet {

void preprocess_320_to_160(hls::stream<axis64_t> &input,
                           hls::stream<QuantizedRgb> &output,
                           ap_uint<32> &status,
                           ap_uint<32> &word_count,
                           ap_uint<32> &saturation_count,
                           ap_uint<64> &work_count);

}  // namespace edgedet

#endif
