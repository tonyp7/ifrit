#!/usr/bin/env bash
# Builds the combined ifrit app image standalone (i.e. outside `docker compose
# up --build`) — useful for tagging a specific version or pushing to a registry.
# See specs/architecture/infra.md § Containerisation.
#
# Usage:
#   docker/build.sh                          # -> ifrit-app:latest
#   IMAGE_TAG=v1.2.3 docker/build.sh          # -> ifrit-app:v1.2.3
#   IMAGE_NAME=registry.example/ifrit-app docker/build.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

IMAGE_NAME="${IMAGE_NAME:-ifrit-app}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

docker build -f docker/Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"
