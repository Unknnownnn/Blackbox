FROM python:3.11-slim-bookworm AS build

WORKDIR /opt/blackbox

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

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-bookworm AS release

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libffi8 \
        libssl3 \
        default-libmysqlclient-dev \
        curl \
        netcat-traditional \
        ca-certificates \
        gnupg \
        lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/blackbox

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN useradd -m -u 1001 blackbox

RUN groupadd -g 999 docker || true && \
    usermod -aG docker blackbox || true

RUN mkdir -p /var/uploads/logos /var/uploads/challenges /var/uploads/temp /var/log/blackbox /opt/blackbox/logs && \
    chmod -R 777 /var/uploads && \
    chmod -R 755 /var/log/blackbox /opt/blackbox/logs

RUN chmod +x /opt/blackbox/docker-entrypoint.sh

RUN chown -R blackbox:blackbox /opt/blackbox /var/uploads /var/log/blackbox

USER blackbox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/opt/blackbox/docker-entrypoint.sh"]
