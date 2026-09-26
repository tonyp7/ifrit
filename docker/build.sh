#!/usr/bin/env bash
# Builds the combined ifrit app image standalone (i.e. outside `docker compose
# up --build`) — useful for tagging a specific version or pushing to a registry.
#
# Usage:
#   docker/build.sh                          # -> ifrit:latest
#   IMAGE_TAG=v1.2.3 docker/build.sh          # -> ifrit:v1.2.3
#   IMAGE_NAME=registry.example/ifrit docker/build.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

IMAGE_NAME="${IMAGE_NAME:-ifrit}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

docker build --no-cache -f docker/Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"
