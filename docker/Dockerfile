FROM python:3.10-slim

# Install git and curl
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone aphrodite-engine repo
RUN git clone https://github.com/PygmalionAI/aphrodite-engine.git /app

# Set environment variables
ENV APHRODITE_TARGET_DEVICE=openvino
ENV APHRODITE_OPENVINO_KVCACHE_SPACE=8
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV HF_HOME=/root/.cache/huggingface

# Create cache directory
RUN mkdir -p /root/.cache/huggingface/hub

# Install dependencies
RUN pip install --no-cache-dir -r requirements-openvino.txt && \
    pip install --no-cache-dir -e .

# Copy the entrypoint script
COPY run_aphrodite.py /app/run_aphrodite.py
RUN chmod +x /app/run_aphrodite.py

# Expose the port used by the Aphrodite server
EXPOSE 2242

# Set entrypoint
ENTRYPOINT ["python", "/app/run_aphrodite.py"]