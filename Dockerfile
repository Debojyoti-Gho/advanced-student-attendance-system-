# Step 1: Use the base image
FROM python:3.10.10-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Copy the requirements.txt and the rest of the code
COPY requirements.txt .
COPY . .

# Step 4: Install system dependencies and Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    wget \
    && pip install --no-cache-dir -r requirements.txt

# Step 5: Expose port (optional)
EXPOSE 8501

# Step 6: Start the Streamlit app
CMD ["streamlit", "run", "attendance.py"]
