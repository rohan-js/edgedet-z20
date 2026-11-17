#ifndef EDGEDET_LAYER_SCHEDULE_HPP
#define EDGEDET_LAYER_SCHEDULE_HPP

namespace edgedet {

enum class LayerKind { kConv3x3, kConv1x1, kUpsampleAdd, kDetectionHead };

struct LayerSpec {
  const char *name;
  LayerKind kind;
  int input_width;
  int input_channels;
  int output_width;
  int output_channels;
  int stride;
};

// The decision-complete network schedule used by the model exporter and the
// eventual generated detector implementation. The checked-in detector.cpp
// exercises the public stream ABI but does not claim to execute these trained
// layers until EDZ_MODEL_WEIGHTS_PRESENT is generated as 1.
constexpr LayerSpec kLayerSchedule[] = {
    {"stem", LayerKind::kConv3x3, 160, 3, 80, 16, 2},
    {"stage1_down", LayerKind::kConv3x3, 80, 16, 40, 24, 2},
    {"stage1_refine", LayerKind::kConv3x3, 40, 24, 40, 24, 1},
    {"stage2_down", LayerKind::kConv3x3, 40, 24, 20, 48, 2},
    {"stage2_refine", LayerKind::kConv3x3, 20, 48, 20, 48, 1},
    {"stage3_down", LayerKind::kConv3x3, 20, 48, 10, 96, 2},
    {"stage3_refine", LayerKind::kConv3x3, 10, 96, 10, 96, 1},
    {"lateral", LayerKind::kConv1x1, 10, 96, 10, 48, 1},
    {"fine_fusion", LayerKind::kUpsampleAdd, 10, 48, 20, 48, 1},
    {"fine_refine", LayerKind::kConv3x3, 20, 48, 20, 48, 1},
    {"fine_head", LayerKind::kDetectionHead, 20, 48, 20, 11, 1},
    {"coarse_head", LayerKind::kDetectionHead, 10, 96, 10, 11, 1},
};

constexpr int kLayerCount = sizeof(kLayerSchedule) / sizeof(kLayerSchedule[0]);

}  // namespace edgedet

#endif  // EDGEDET_LAYER_SCHEDULE_HPP
