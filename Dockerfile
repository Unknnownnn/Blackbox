# Multi-stage build for BlackBox CTF Platform
# Stage 1: Build stage with all build dependencies
FROM python:3.11-slim-bookworm AS build

# Set working directory
WORKDIR /opt/blackbox

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        default-libmysqlclient-dev \
        pkg-config \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Release stage with minimal runtime dependencies
FROM python:3.11-slim-bookworm AS release

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libffi8 \
        libssl3 \
        default-libmysqlclient-dev \
        curl \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/blackbox

# Copy virtual environment from build stage
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code (including static/uploads directory)
COPY . .

# Create non-root user
RUN useradd -m -u 1001 blackbox

# Create necessary directories with proper permissions
# Note: /var/uploads is for writable content (logos, challenge files)
# Note: /opt/blackbox is read-only application code
RUN mkdir -p /var/uploads/logos /var/uploads/challenges /var/uploads/temp /var/log/blackbox /opt/blackbox/logs && \
    chmod -R 777 /var/uploads && \
    chmod -R 755 /var/log/blackbox /opt/blackbox/logs

# Make entrypoint script executable
RUN chmod +x /opt/blackbox/docker-entrypoint.sh

# Change ownership of all directories to blackbox user
RUN chown -R blackbox:blackbox /opt/blackbox /var/uploads /var/log/blackbox

# Switch to non-root user
USER blackbox

# Expose port 8000 (Gunicorn will listen here)
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/opt/blackbox/docker-entrypoint.sh"]
