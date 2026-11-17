import vitis
import os
import shutil

# Paths
base_dir = "/media/rohanjs/HDD/UVM/PROJECTS/Real-Time Object Detection Using Hardware-Accelerated CNN on Xilinx Zynq FPGA with Arm Processor"
workspace = "/tmp/vitis_workspace"
xsa_file = "/tmp/no_space_path/cnn_system_wrapper.xsa"
src_dir = os.path.join(base_dir, "sw/src")
weights_dir = os.path.join(base_dir, "sw/weights")

print(f"Creating Vitis Workspace at {workspace}...")
if os.path.exists(workspace):
    shutil.rmtree(workspace)
os.makedirs(workspace, exist_ok=True)

client = vitis.create_client()
client.set_workspace(workspace)

# 1. Create Platform Component
print("Creating Platform Component...")
platform = client.create_platform_component(
    name="zedboard_platform",
    hw_design=xsa_file,
    os="standalone",
    cpu="ps7_cortexa9_0"
)
print("Building Platform...")
platform.build()

# 2. Create Application Component
print("Creating Application Component...")
xpfm_path = os.path.join(workspace, "zedboard_platform", "export", "zedboard_platform", "zedboard_platform.xpfm")
app = client.create_app_component(
    name="cnn_app",
    platform=xpfm_path,
    domain="standalone_ps7_cortexa9_0",
    template="empty_C"
)

# 3. Import Sources
print("Importing C source files and weights...")
app.import_files(from_loc=src_dir, files=["main.c", "weights.h"], dest_dir_in_cmp="src")
app.import_files(from_loc=weights_dir, files=[
    "conv1_weights.inc", "conv1_bias.inc",
    "conv2_weights.inc", "conv2_bias.inc",
    "fc_weights.inc", "fc_bias.inc"
], dest_dir_in_cmp="src")

# 4. Configure Compiler Flags (-O3 for performance)
# Vitis Unified IDE syntax for compiler flags
# We skip complex flags for now, default is usually ok, but we can try to set it via app settings if needed.

# 5. Build Application
print("Building Application...")
app.build()

print("="*50)
print("Build Complete!")
print(f"ELF binary generated at: {workspace}/cnn_app/build/cnn_app.elf")
print("="*50)
