#!/bin/bash

# Install cmake
curl -LO https://cmake.org/files/v3.31/cmake-3.31.4.tar.gz
tar -xzvf cmake-3.31.4.tar.gz
cd cmake-3.31.4
./bootstrap && make && sudo make install

# Install dlib dependency
sudo apt-get update
sudo apt-get install -y build-essential

# Now you can install Python dependencies from requirements.txt
pip install --no-cache-dir -r requirements.txt
