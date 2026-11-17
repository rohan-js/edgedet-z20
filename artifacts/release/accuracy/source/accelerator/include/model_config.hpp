#ifndef EDGEDET_MODEL_CONFIG_HPP
#define EDGEDET_MODEL_CONFIG_HPP

#include <ap_int.h>

// The model exporter is expected to replace this header (or put an earlier
// generated include directory on the compiler search path). The checked-in
// constants deliberately describe an interface-test scaffold, not a trained
// road-safety detector.
#ifndef EDZ_MODEL_WEIGHTS_PRESENT
#define EDZ_MODEL_WEIGHTS_PRESENT 0
#endif
#ifndef EDZ_MODEL_PACKAGE_VERSION
#define EDZ_MODEL_PACKAGE_VERSION 0
#endif

#ifndef EDZ_PE
#define EDZ_PE 8
#endif

#ifndef EDZ_SIMD
#define EDZ_SIMD 8
#endif

#if (EDZ_PE != 4) && (EDZ_PE != 8)
#error "Supported checked-in PE values are 4 and 8"
#endif

#if (EDZ_SIMD != 8) && (EDZ_SIMD != 16)
#error "Supported checked-in SIMD values are 8 and 16"
#endif

namespace edgedet {
namespace model {

constexpr int kPe = EDZ_PE;
constexpr int kSimd = EDZ_SIMD;
constexpr int kOutputFractionBits = 8;

// Canonical preprocessing shared with model/constants.py:
// q = sat_int8(round_away((avg_u8 * multiplier + bias) / 2^20)).
constexpr int kInputMultiplier[3] = {574611, 587438, 584827};
constexpr int kInputBias[3] = {-71065063, -68307237, -60547108};
constexpr int kInputRightShift = 20;

// Structural placeholder projection for interface tests. It is intentionally
// weak and untrained. Class/centerness rows are consumed by the scaffold head;
// box distances are fixed positive values in detector.cpp.
constexpr signed char kPlaceholderHeadWeights[7][3] = {
    {1, 0, 0}, {0, 1, 0}, {0, 0, 1}, {1, 1, 0},
    {0, 1, 1}, {1, 0, 1}, {1, 2, 1}};
constexpr short kPlaceholderHeadBias[7] = {
    -1024, -1024, -1024, -1152, -1152, -1152, -256};

}  // namespace model
}  // namespace edgedet

#endif  // EDGEDET_MODEL_CONFIG_HPP
