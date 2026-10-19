#!/bin/bash
set -euo pipefail
export PATH="$PATH:/snap/bin"

cd /home/ubuntu/masareef
BUCKET="masareef-backups-478769829073"
STAMP="$(date -u +%Y-%m-%d)"
TMP="$(mktemp -d)"

for name in masareef checkpoints; do
    docker compose exec -T bot python -c "import sqlite3; s = sqlite3.connect('/data/$name.db'); d = sqlite3.connect('/tmp/$name.db'); s.backup(d); d.close()"
    docker compose cp "bot:/tmp/$name.db" "$TMP/$name.db"
    aws s3 cp "$TMP/$name.db" "s3://$BUCKET/$STAMP/$name.db" --region eu-north-1 --only-show-errors
done

rm -rf "$TMP"
echo "$(date) backup $STAMP ok"