# Third-party dependencies

The active project expects the following independently licensed components:

- AMD Vivado/Vitis and generated Xilinx drivers/IP.
- PyTorch and torchvision.
- NumPy, OpenCV, PyYAML and pytest.
- PySide6 and pyqtgraph for the optional desktop dashboard.
- BDD100K data obtained directly from Berkeley DeepDrive.
- YOLOX teacher code/checkpoints when knowledge distillation is enabled.

Generated releases must include the exact dependency versions and preserve
all notices required by those projects. First-party EdgeDet-Z20 code is
released under the MIT license (see LICENSE); the notices above still apply
to the third-party components.
