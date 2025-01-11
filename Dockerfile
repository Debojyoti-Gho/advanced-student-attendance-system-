# Use an official Python base image
FROM python:3.9-slim

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED 1

# Install dependencies for building dlib
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    wget \
    libopenblas-dev \
    liblapack-dev \
    python3-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Set a working directory
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Streamlit app files into the container
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "app.py"]
