# Use an official Python runtime as the base image
FROM python:3.8-slim

# Set environment variables to prevent Python from writing pyc files to disc
# and to make the output of Python unbuffered.
ENV PYTHONUNBUFFERED 1

# Install system dependencies including CMake and build-essential
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt into the container
COPY requirements.txt /app/

# Install the Python dependencies inside the container
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app's files into the container
COPY . /app/

# Expose the Streamlit port (default is 8501)
EXPOSE 8501

# Command to run the app using Streamlit
CMD ["streamlit", "run", "app.py"]
