#!/bin/bash
set -e

echo "=== OpenVSP & Open3D Installation Script ==="
echo "Note: OpenVSP binaries for Ubuntu are hosted on openvsp.org."
echo "Please download the OpenVSP Ubuntu 22.04 zip file from http://openvsp.org/download.php"
echo "Extract it to: $(pwd)/thirdparty/openvsp"
echo ""
echo "Installing Open3D..."
conda run -n aero pip install open3d

echo ""
echo "Setting up OpenVSP Python API path..."
# Assuming user extracts it to thirdparty/openvsp
OPEN_VSP_PYTHON_PATH="$(pwd)/thirdparty/openvsp/python"

echo "To use OpenVSP in the 'aero' environment, we will add it to conda's pth."
CONDA_SP_DIR=$(conda run -n aero python -c "import site; print(site.getsitepackages()[0])")

if [ -d "$OPEN_VSP_PYTHON_PATH" ]; then
    echo "$OPEN_VSP_PYTHON_PATH" > "$CONDA_SP_DIR/openvsp.pth"
    echo "Added OpenVSP to python path."
else
    echo "WARNING: $OPEN_VSP_PYTHON_PATH not found."
    echo "Please download and extract OpenVSP, then manually create openvsp.pth in $CONDA_SP_DIR"
fi

echo "Installation setup completed."
