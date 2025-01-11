# Use an official Python image from the DockerHub
FROM python:3.8-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (for dlib and other packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dlib via pip
RUN pip install dlib

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on (optional, depending on your app)
EXPOSE 8501

# Run the application (assuming Streamlit app)
CMD ["streamlit", "run", "app.py"]
