#include <cstdlib>
#include <iostream>

#include "edgedet_types.hpp"
#include "generated_model.hpp"
#include "model_config.hpp"
#include "preprocess.hpp"

using edgedet::axis64_t;

namespace {

int expected_normalized(unsigned value, int channel) {
  long long scaled = static_cast<long long>(value) *
                         edgedet::model::kInputMultiplier[channel] +
                     edgedet::model::kInputBias[channel];
  const long long half = 1LL << (edgedet::model::kInputRightShift - 1);
  long long rounded = scaled >= 0
                          ? (scaled + half) >> edgedet::model::kInputRightShift
                          : -(((-scaled) + half) >> edgedet::model::kInputRightShift);
  if (rounded < -128) rounded = -128;
  if (rounded > 127) rounded = 127;
  return static_cast<int>(rounded);
}

axis64_t make_word(unsigned char r,
                   unsigned char g,
                   unsigned char b,
                   bool last,
                   bool bad_keep,
                   bool bad_strb) {
  axis64_t word;
  word.data = 0;
  word.data.range(7, 0) = r;
  word.data.range(15, 8) = g;
  word.data.range(23, 16) = b;
  word.data.range(31, 24) = r;
  word.data.range(39, 32) = g;
  word.data.range(47, 40) = b;
  word.keep = bad_keep ? 0x3F : 0xFF;
  word.strb = bad_strb ? 0x3F : 0xFF;
  word.last = last;
  return word;
}

bool run_case(bool early_tlast, bool omit_final_tlast,
              bool bad_keep = false, bool bad_strb = false) {
  hls::stream<axis64_t> input;
  hls::stream<axis64_t> output;
  for (int i = 0; i < edgedet::kInputWords; ++i) {
    bool last = (i == edgedet::kInputWords - 1) && !omit_final_tlast;
    if (early_tlast && i == 17) last = true;
    input.write(make_word(static_cast<unsigned char>(i & 0xFF), 64, 192,
                          last, bad_keep && i == 9, bad_strb && i == 13));
  }

  ap_uint<32> status = 0;
  ap_uint<32> frame_id_out = 0;
  ap_uint<32> input_words = 0;
  ap_uint<32> output_words = 0;
  ap_uint<32> saturations = 0;
  ap_uint<32> model_crc = 0;
  ap_uint<64> work = 0;
  edgedet_top(input, output, 0x12345678u, status, frame_id_out, input_words,
              output_words, saturations, model_crc, work);

  bool ok = true;
  ok &= (frame_id_out == 0x12345678u);
  ok &= (input_words == edgedet::kInputWords);
  ok &= (output_words == edgedet::kOutputWords);
  ok &= (model_crc == edgedet::generated::kModelCrc);
#if EDZ_MODEL_WEIGHTS_PRESENT
  ok &= ((status & edgedet::kStatusPlaceholderModel) == 0);
#else
  ok &= ((status & edgedet::kStatusPlaceholderModel) != 0);
#endif
  ok &= (((status & edgedet::kStatusEarlyTlast) != 0) == early_tlast);
  ok &= (((status & edgedet::kStatusMissingTlast) != 0) == omit_final_tlast);
  ok &= (((status & edgedet::kStatusBadKeep) != 0) == bad_keep);
  ok &= (((status & edgedet::kStatusBadStrb) != 0) == bad_strb);
  ok &= (work > 0);

  int value_count = 0;
  for (int i = 0; i < edgedet::kOutputWords; ++i) {
    if (output.empty()) {
      std::cerr << "Output ended at word " << i << "\n";
      return false;
    }
    axis64_t word = output.read();
    ok &= (word.keep == 0xFF);
    ok &= (word.strb == 0xFF);
    ok &= (static_cast<bool>(word.last) == (i == edgedet::kOutputWords - 1));
    for (int lane = 0; lane < 4; ++lane) {
      ap_int<16> value = word.data.range(16 * lane + 15, 16 * lane);
      const int field = value_count % edgedet::kFieldsPerCell;
#if !EDZ_MODEL_WEIGHTS_PRESENT
      if (field >= edgedet::kLeft) ok &= (value > 0);
#endif
      ++value_count;
    }
  }
  ok &= output.empty();
  ok &= (value_count == edgedet::kOutputValues);
  if (!ok) {
    std::cerr << "Case failed: early=" << early_tlast
              << " omit_final=" << omit_final_tlast
              << " bad_keep=" << bad_keep << " bad_strb=" << bad_strb
              << " status=0x" << std::hex << status.to_uint() << std::dec
              << " values=" << value_count << "\n";
  }
  return ok;
}

bool test_preprocess_exact() {
  hls::stream<axis64_t> input;
  hls::stream<edgedet::QuantizedRgb> output;
  for (int i = 0; i < edgedet::kInputWords; ++i) {
    input.write(make_word(0, 127, 255, i == edgedet::kInputWords - 1,
                          false, false));
  }
  ap_uint<32> status = 0, words = 0, saturations = 0;
  ap_uint<64> work = 0;
  edgedet::preprocess_320_to_160(input, output, status, words, saturations,
                                 work);
  bool ok = words == edgedet::kInputWords;
  ok &= ((status & ~edgedet::kStatusPlaceholderModel) == 0);
  for (int i = 0; i < edgedet::kNetworkWidth * edgedet::kNetworkHeight; ++i) {
    if (output.empty()) return false;
    edgedet::QuantizedRgb pixel = output.read();
    ok &= static_cast<int>(pixel.r) == expected_normalized(0, 0);
    ok &= static_cast<int>(pixel.g) == expected_normalized(127, 1);
    ok &= static_cast<int>(pixel.b) == expected_normalized(255, 2);
  }
  return ok && output.empty();
}

}  // namespace

int main() {
  bool ok = test_preprocess_exact();
  ok &= run_case(false, false);
  ok &= run_case(true, false);
  ok &= run_case(false, true);
  ok &= run_case(false, false, true, true);
  std::cout << (ok ? "EdgeDet HLS C simulation PASSED\n"
                   : "EdgeDet HLS C simulation FAILED\n");
  return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
