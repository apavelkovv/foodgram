#!/bin/sh
set -eu
cd "$(dirname "$0")"
: "${IMAGE_PREFIX:?Set IMAGE_PREFIX}"
: "${IMAGE_TAG:?Set IMAGE_TAG to a commit SHA}"
test -f .env
export IMAGE_PREFIX IMAGE_TAG
# Use existing sudo rights when the SSH account cannot access the Docker socket.
if ! docker info >/dev/null 2>&1; then
    docker() {
        sudo -n env IMAGE_PREFIX="$IMAGE_PREFIX" IMAGE_TAG="$IMAGE_TAG" docker "$@"
    }
fi
docker compose -f docker-compose.production.yml pull
# Recreate the one-shot frontend container so the volume receives this release.
docker compose -f docker-compose.production.yml up -d --force-recreate frontend
docker compose -f docker-compose.production.yml up -d --wait --wait-timeout 180 db backend nginx
docker compose -f docker-compose.production.yml exec -T --user foodgram backend python manage.py import_catalog
docker compose -f docker-compose.production.yml up -d --no-deps --force-recreate nginx
docker compose -f docker-compose.production.yml exec -T nginx nginx -t

docker compose -f docker-compose.production.yml exec -T nginx wget -q --header='X-Forwarded-Proto: https' -O /dev/null http://127.0.0.1/api/tags/
