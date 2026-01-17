# -----------------------------
# 1) Builder Stage
# -----------------------------
    FROM python:3.11-slim AS builder

    WORKDIR /app
    
    # install build dependencies (safe for pyyaml)
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*
    
    COPY requirements.txt .
    
    RUN pip install --no-cache-dir --upgrade pip
    RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt
    
    
    # -----------------------------
    # 2) Runtime Stage
    # -----------------------------
    FROM python:3.11-slim AS runtime
    
    WORKDIR /app
    
    # copy wheels and install them
    COPY --from=builder /wheels /wheels
    RUN pip install --no-cache-dir /wheels/*
    
    # copy your MCP server code
    COPY . .
    
    # expose MCP server port
    EXPOSE 8000
    
    # Healthcheck (calls /health route)
    HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
      CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1
    
    # Run the MCP server
    CMD ["python", "mcp_server.py"]
    