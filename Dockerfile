# Multi-stage build for CTFd clone
# Stage 1: Build stage with all build dependencies
FROM python:3.11-slim-bookworm AS build

# Set working directory
WORKDIR /opt/ctf

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
WORKDIR /opt/ctf

# Copy virtual environment from build stage
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /var/uploads /var/log/CTFd /opt/ctf/logs && \
    chmod -R 777 /var/uploads && \
    chmod -R 755 /var/log/CTFd /opt/ctf/logs

# Create non-root user (matching CTFd's user ID)
RUN useradd -m -u 1001 ctf

# Make entrypoint script executable BEFORE changing ownership
RUN chmod +x /opt/ctf/docker-entrypoint.sh

# Change ownership AFTER all files are in place
RUN chown -R ctf:ctf /opt/ctf /var/log/CTFd

# IMPORTANT: Don't set ownership of /var/uploads here
# Docker volumes will be mounted on top and inherit host permissions
# We'll handle this in entrypoint script

# Switch to non-root user
USER ctf

# Expose port 8000 (Gunicorn will listen here)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/opt/ctf/docker-entrypoint.sh"]
