#!/bin/bash
# Installation script for Singapore Enablement Workshop
# This script handles common installation issues

set -e  # Exit on error

echo "=========================================="
echo "Singapore Enablement Workshop Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet
echo "✓ pip upgraded"
echo ""

# Install pyarrow first (pre-built binary to avoid CMake issues)
echo "Installing pyarrow (pre-built binary)..."
pip install pyarrow==14.0.1 --only-binary=:all: --quiet
echo "✓ pyarrow installed"
echo ""

# Install core dependencies
echo "Installing core AWS and SageMaker packages..."
pip install boto3>=1.34.0 sagemaker>=2.200.0 --quiet
echo "✓ Core packages installed"
echo ""

# Install data processing packages
echo "Installing data processing packages..."
pip install pandas>=2.0.0 numpy>=1.24.0 --quiet
echo "✓ Data processing packages installed"
echo ""

# Install ML packages (with error handling)
echo "Installing ML packages..."
pip install transformers>=4.36.0 accelerate>=0.25.0 peft>=0.7.0 datasets>=2.16.0 --quiet || {
    echo "⚠ Some ML packages failed to install. Trying without bitsandbytes..."
    pip install transformers>=4.36.0 accelerate>=0.25.0 peft>=0.7.0 datasets>=2.16.0 --quiet
}
echo "✓ ML packages installed"
echo ""

# Try to install bitsandbytes (optional, may fail on some platforms)
echo "Installing bitsandbytes (optional)..."
pip install bitsandbytes>=0.41.0 --quiet 2>/dev/null && echo "✓ bitsandbytes installed" || echo "⚠ bitsandbytes skipped (not critical)"
echo ""

# Install agentic framework
echo "Installing strands-agents..."
pip install strands-agents>=0.1.6 --quiet
echo "✓ strands-agents installed"
echo ""

# Install utilities
echo "Installing utilities..."
pip install tqdm>=4.66.0 ipython>=8.0.0 ipywidgets>=8.0.0 --quiet
echo "✓ Utilities installed"
echo ""

# Install dependency fixes
echo "Installing dependency fixes..."
pip install "protobuf>=4.25.0,<5.0.0" opentelemetry-proto>=1.33.1 starlette>=0.46.2 "rich>=14.0.0,<15.0.0" --quiet
echo "✓ Dependencies fixed"
echo ""

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Installed packages:"
pip list | grep -E "(boto3|sagemaker|pandas|numpy|pyarrow|transformers|accelerate|peft|datasets|strands-agents)"
echo ""
echo "You can now run the workshop notebooks!"
echo ""
