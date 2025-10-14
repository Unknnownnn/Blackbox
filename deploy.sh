#!/bin/bash
# Production deployment script for CTF Platform

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=================================================="
echo "  CTF Platform - Production Deployment"
echo -e "==================================================${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo or as root${NC}"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Detect docker-compose command
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo -e "${YELLOW}[1/6] Checking environment...${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}  Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}  ⚠ IMPORTANT: Edit .env and set production values!${NC}"
    echo -e "${RED}     Especially: SECRET_KEY, database passwords${NC}"
    read -p "Press Enter after editing .env, or Ctrl+C to exit..."
fi

echo -e "${GREEN}  ✓ Environment check complete${NC}"

# Create necessary directories
echo -e "${YELLOW}[2/6] Creating data directories...${NC}"
mkdir -p .data/CTFPlatform/{logs,uploads}
mkdir -p .data/mysql
mkdir -p .data/redis
mkdir -p conf/nginx

echo -e "${GREEN}  ✓ Directories created${NC}"

# Set permissions
echo -e "${YELLOW}[3/6] Setting permissions...${NC}"
chown -R 1001:1001 .data/CTFPlatform
chmod -R 755 .data/CTFPlatform

echo -e "${GREEN}  ✓ Permissions set${NC}"

# Make entrypoint executable
echo -e "${YELLOW}[4/6] Preparing Docker build...${NC}"
chmod +x docker-entrypoint.sh

echo -e "${GREEN}  ✓ Build preparation complete${NC}"

# Build and start containers
echo -e "${YELLOW}[5/6] Building and starting containers...${NC}"
echo -e "${CYAN}  This may take several minutes on first run...${NC}"

$DOCKER_COMPOSE down 2>/dev/null || true
$DOCKER_COMPOSE build --no-cache
$DOCKER_COMPOSE up -d

echo -e "${GREEN}  ✓ Containers started${NC}"

# Wait for services to be healthy
echo -e "${YELLOW}[6/6] Waiting for services to be ready...${NC}"
sleep 10

# Check container status
echo -e "${CYAN}Container Status:${NC}"
$DOCKER_COMPOSE ps

echo ""
echo -e "${GREEN}=================================================="
echo "  Deployment Complete!"
echo -e "==================================================${NC}"
echo ""
echo -e "${CYAN}Access the platform:${NC}"
echo "  HTTP: http://localhost"
echo "  Direct: http://localhost:8000"
echo ""
echo -e "${CYAN}Default admin credentials:${NC}"
echo "  Username: admin"
echo "  Password: admin123"
echo -e "${RED}  ⚠ CHANGE THESE IMMEDIATELY!${NC}"
echo ""
echo -e "${CYAN}View logs:${NC}"
echo "  docker-compose logs -f ctf"
echo ""
echo -e "${CYAN}Stop platform:${NC}"
echo "  docker-compose down"
echo ""
echo -e "${CYAN}Restart platform:${NC}"
echo "  docker-compose restart"
echo ""
echo -e "${YELLOW}⚠ Security Reminders:${NC}"
echo "  1. Change SECRET_KEY in .env"
echo "  2. Change all default passwords"
echo "  3. Set up SSL/TLS certificates"
echo "  4. Configure firewall rules"
echo "  5. Regular backups of .data/ directory"
echo ""
