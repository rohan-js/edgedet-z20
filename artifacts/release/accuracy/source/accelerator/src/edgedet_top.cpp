#include "edgedet_types.hpp"

#include "detector.hpp"
#include "generated_model.hpp"
#include "preprocess.hpp"

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
    ap_uint<64> &work_count) {
#pragma HLS INTERFACE axis port=s_axis_pixels
#pragma HLS INTERFACE axis port=m_axis_predictions
#pragma HLS INTERFACE s_axilite port=frame_id bundle=control
#pragma HLS INTERFACE s_axilite port=status bundle=control
#pragma HLS INTERFACE s_axilite port=frame_id_out bundle=control
#pragma HLS INTERFACE s_axilite port=input_words bundle=control
#pragma HLS INTERFACE s_axilite port=output_words bundle=control
#pragma HLS INTERFACE s_axilite port=saturation_count bundle=control
#pragma HLS INTERFACE s_axilite port=model_crc bundle=control
#pragma HLS INTERFACE s_axilite port=work_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS DATAFLOW

  hls::stream<edgedet::QuantizedRgb> quantized_pixels("quantized_pixels");
  hls::stream<edgedet::output_t> prediction_values("prediction_values");
#pragma HLS STREAM variable=quantized_pixels depth=256
#pragma HLS STREAM variable=prediction_values depth=64

  ap_uint<32> preprocess_saturations = 0;
  ap_uint<32> detector_saturations = 0;
  ap_uint<64> preprocess_work = 0;
  ap_uint<64> detector_work = 0;
  ap_uint<64> pack_work = 0;

  edgedet::preprocess_320_to_160(
      s_axis_pixels, quantized_pixels, status, input_words,
      preprocess_saturations, preprocess_work);
  edgedet::detector_scaffold(quantized_pixels, prediction_values,
                             detector_saturations, detector_work);
  edgedet::pack_predictions(prediction_values, m_axis_predictions,
                            output_words, pack_work);

  frame_id_out = frame_id;
  saturation_count = preprocess_saturations + detector_saturations;
  model_crc = edgedet::generated::kModelCrc;
  // Algorithmic work tokens, not measured wall-clock cycles. Real cycle timing
  // comes from HLS/implementation reports or a PS timer around DMA execution.
  work_count = preprocess_work + detector_work + pack_work;
}
