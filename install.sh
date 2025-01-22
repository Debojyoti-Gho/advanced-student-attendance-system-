#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status
set -o pipefail  # Consider a pipeline as failed if any command fails

# Update and install required system dependencies
apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-dev \
    bluetooth \
    bluez \
    libbluetooth-dev \
    python3-dev

# Download and extract CMake source
CMAKE_VERSION=3.31.4
curl -LO https://cmake.org/files/v3.31/cmake-${CMAKE_VERSION}.tar.gz
tar -xzvf cmake-${CMAKE_VERSION}.tar.gz
cd cmake-${CMAKE_VERSION}

# Configure and install CMake
./bootstrap --prefix=/opt/cmake
make -j$(nproc)
make install

# Add the local CMake binary to PATH for this session
export PATH=/opt/cmake/bin:$PATH

# Go back to the root directory
cd ..

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
