#ifndef EDGEDET_TYPES_HPP
#define EDGEDET_TYPES_HPP

#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

namespace edgedet {

constexpr int kInputWidth = 320;
constexpr int kInputHeight = 320;
constexpr int kPixelsPerInputWord = 2;
constexpr int kInputWords = kInputWidth * kInputHeight / kPixelsPerInputWord;

constexpr int kNetworkWidth = 160;
constexpr int kNetworkHeight = 160;
constexpr int kFineGrid = 20;
constexpr int kCoarseGrid = 10;
constexpr int kClasses = 6;
constexpr int kFieldsPerCell = 11;
constexpr int kFineValues = kFineGrid * kFineGrid * kFieldsPerCell;
constexpr int kCoarseValues = kCoarseGrid * kCoarseGrid * kFieldsPerCell;
constexpr int kOutputValues = kFineValues + kCoarseValues;
constexpr int kValuesPerOutputWord = 4;
constexpr int kOutputWords = kOutputValues / kValuesPerOutputWord;

static_assert(kOutputValues == 5500, "The public detector tensor ABI is 5,500 int16 values");
static_assert((kOutputValues % kValuesPerOutputWord) == 0,
              "The output tensor must fill complete 64-bit AXI words");

using axis64_t = ap_axiu<64, 0, 0, 0>;
using activation_t = ap_int<8>;
using feature_t = ap_uint<8>;
using weight8_t = ap_int<8>;
using weight4_t = ap_int<4>;
using accumulator_t = ap_int<32>;
using output_t = ap_int<16>;

struct QuantizedRgb {
  activation_t r;
  activation_t g;
  activation_t b;
};

enum StatusBits : unsigned {
  kStatusEarlyTlast = 1u << 0,
  kStatusMissingTlast = 1u << 1,
  kStatusBadKeep = 1u << 2,
  kStatusBadStrb = 1u << 3,
  // This bit is intentionally asserted by the checked-in scaffold. Software must
  // refuse to describe its output as trained detections while it is set.
  kStatusPlaceholderModel = 1u << 31
};

enum OutputField : unsigned {
  kClass0 = 0,
  kClass1 = 1,
  kClass2 = 2,
  kClass3 = 3,
  kClass4 = 4,
  kClass5 = 5,
  kCenterness = 6,
  kLeft = 7,
  kTop = 8,
  kRight = 9,
  kBottom = 10
};

}  // namespace edgedet

extern "C" void edgedet_top(
    hls::stream<edgedet::axis64_t> &s_axis_pixels,
    hls::stream<edgedet::axis64_t> &m_axis_predictions,
    ap_uint<32> frame_id,
    ap_uint<32> &status,
    ap_uint<32> &frame_id_out,
    ap_uint<32> &input_words,
    ap_uint<32> &output_words,
    ap_uint<32> &saturation_count,
    ap_uint<32> &model_crc,
    ap_uint<64> &work_count);

#endif  // EDGEDET_TYPES_HPP
