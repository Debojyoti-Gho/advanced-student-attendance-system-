#!/bin/bash

# Update and install dependencies required to build CMake
apt-get update && apt-get install -y build-essential curl

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
pip install --no-cache-dir -r requirements.txt
