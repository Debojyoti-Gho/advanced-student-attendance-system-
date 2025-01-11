FROM python:3.12-slim

# Install required system dependencies
RUN apt-get update && \
    apt-get install -y cmake build-essential

# Set up working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Expose the app on port 8501
EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "attendance.py"]
