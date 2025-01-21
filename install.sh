#!/bin/bash

# Install cmake
curl -LO https://cmake.org/files/v3.31/cmake-3.31.4.tar.gz
tar -xzvf cmake-3.31.4.tar.gz
cd cmake-3.31.4
./bootstrap && make && make install
cd ..

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

