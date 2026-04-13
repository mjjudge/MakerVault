#!/usr/bin/env bash
# bootstrap.sh — Set up a local MakerVault development environment
#
# This script is a placeholder. It will be expanded as the application is built.
# Prerequisites (to be installed manually for now):
#   - Docker and Docker Compose
#   - Python 3.12+
#   - Node.js 20+
#   - make

set -euo pipefail

echo "MakerVault bootstrap — early scaffold stage"
echo "============================================"
echo ""
echo "This script will set up the local development environment."
echo "Currently this is a placeholder — implementation not yet complete."
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    echo "Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

echo "✓ Docker found: $(docker --version)"

# Check for Docker Compose
if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose (v2) is not available."
    echo "Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker Compose found: $(docker compose version)"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH."
    exit 1
fi

echo "✓ Python found: $(python3 --version)"

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed or not in PATH."
    exit 1
fi

echo "✓ Node.js found: $(node --version)"

echo ""
echo "All prerequisites found."
echo ""
echo "Next steps (manual for now — to be automated in a future phase):"
echo "  1. Copy infra/docker/.env.example to infra/docker/.env and configure it"
echo "  2. Run: docker compose -f infra/docker/docker-compose.yml up -d"
echo "  3. Access the app at http://localhost"
echo ""
echo "See docs/ROADMAP.md for what has and has not been implemented yet."
