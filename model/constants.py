from __future__ import annotations

CLASSES = ("person", "bicycle", "motorcycle", "car", "bus", "truck")
CLASS_TO_ID = {name: index for index, name in enumerate(CLASSES)}
BDD_CLASS_MAP = {
    "person": "person",
    "rider": "person",
    "bike": "bicycle",
    "motor": "motorcycle",
    "car": "car",
    "bus": "bus",
    "truck": "truck",
}
BDD_IMAGE_WIDTH = 1280
BDD_IMAGE_HEIGHT = 720
CANVAS_SIZE = 320
NETWORK_SIZE = 160
HEAD_CHANNELS = 11
STRIDES = (8, 16)
OUTPUT_VALUES = 20 * 20 * HEAD_CHANNELS + 10 * 10 * HEAD_CHANNELS
PAD_RGB = (114, 114, 114)
NORMALIZE_MEAN = (0.485, 0.456, 0.406)
NORMALIZE_STD = (0.229, 0.224, 0.225)
INPUT_QUANT_SCALE = 1.0 / 32.0
OUTPUT_SCALE = 1.0 / 256.0

# Canonical fixed-point RGB normalization shared by Python and HLS. For each
# reduced uint8 channel: q = round_away((pixel * multiplier + bias) / 2**20).
# Keeping this integer boundary explicit avoids small host/HLS differences from
# floating-point mean/std evaluation.
PREPROCESS_FRACTION_BITS = 20
PREPROCESS_MULTIPLIER = (574611, 587438, 584827)
PREPROCESS_BIAS = (-71065063, -68307237, -60547108)
