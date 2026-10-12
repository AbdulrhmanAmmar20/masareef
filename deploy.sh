#!/bin/bash
cd /home/ubuntu/masareef

git fetch -q origin master

if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/master)" ]; then
    git pull -q
    docker compose up -d --build
    echo "$(date) deployed $(git rev-parse --short HEAD)"
fi