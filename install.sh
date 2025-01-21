#!/bin/bash

# Update and install required packages (adjust for Render's base image)
apt-get update && apt-get install -y build-essential cmake curl

# Install cmake from source
curl -LO https://cmake.org/files/v3.31/cmake-3.31.4.tar.gz
tar -xzvf cmake-3.31.4.tar.gz
cd cmake-3.31.4
./bootstrap && make && make install
cd ..

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt
