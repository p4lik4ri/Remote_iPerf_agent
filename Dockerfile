# Step 1: Use a lightweight base image
FROM python:3.10-slim

# Step 2: Set the working directory
WORKDIR /app

# Step 3: Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf \
    iperf3 \
    net-tools \
    iputils-ping \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Step 4: Copy application files into the container
COPY . .

# Step 5: Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Expose required ports (Flask and iPerf ports)
EXPOSE 5000         
EXPOSE 5001/tcp     
EXPOSE 5001/udp     

# Step 7: Run the Flask application
CMD ["flask", "run", "-h", "0.0.0.0"]
