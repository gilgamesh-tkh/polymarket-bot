# Multi-stage build for Polymarket Smart Money Detection

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/
COPY setup.py .
COPY README.md .

# Install the package
RUN pip install -e .

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 polymarket && \
    chown -R polymarket:polymarket /app
USER polymarket

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and configs
COPY --chown=polymarket:polymarket src/ ./src/
COPY --chown=polymarket:polymarket config/ ./config/
COPY --chown=polymarket:polymarket setup.py .
COPY --chown=polymarket:polymarket README.md .

# Create necessary directories
RUN mkdir -p data results logs notebooks external

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_URL=duckdb:///app/data/polymarket_data.duckdb
ENV CONFIG_FILE=/app/config/config.yaml

# Expose ports
EXPOSE 8501 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/ || exit 1

# Default command
CMD ["streamlit", "run", "src/visualization/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Development stage with Jupyter
FROM runtime as development

# Install development dependencies
COPY requirements.txt .
RUN pip install --no-cache-dev -r requirements.txt

# Copy notebooks
COPY --chown=polymarket:polymarket notebooks/ ./notebooks/

# Expose Jupyter port
EXPOSE 8888

# Command for development
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]

# Production stage with optimizations
FROM runtime as production

# Optimize for production
ENV PYTHONOPTIMIZE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Add non-root user
USER polymarket

# Production command
CMD ["streamlit", "run", "src/visualization/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCaching=true"]