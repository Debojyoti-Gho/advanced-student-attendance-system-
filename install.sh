#!/bin/bash

# Install required system dependencies for bleak
apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-dev \
    bluetooth \
    bluez \
    libbluetooth-dev \
    python3-dev
    
# Download and extract CMake source
curl -LO https://cmake.org/files/v3.31/cmake-3.31.4.tar.gz
tar -xzvf cmake-3.31.4.tar.gz
cd cmake-3.31.4

# Configure CMake to install locally (e.g., under /opt/cmake)
./bootstrap --prefix=/opt/cmake
make
make install

# Add the local CMake binary to PATH
export PATH=/opt/cmake/bin:$PATH

# Go back to the root directory
cd ..

# Install Python dependencies
pip install -r requirements.txt


