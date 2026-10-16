# Step 1: Use a lightweight base image
FROM python:3.10-slim

# Step 2: Set the working directory
WORKDIR /app

# Step 3: Copy and install Python dependencies first to leverage layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 4: Copy application files into the container
COPY . .

# Step 5: Expose the FastAPI/uvicorn port
EXPOSE 8000

# Step 6: Run the network-monitor orchestrator
CMD ["uvicorn", "main:_app", "--host", "0.0.0.0", "--port", "8000"]
