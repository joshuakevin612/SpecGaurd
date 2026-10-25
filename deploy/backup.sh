#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${SPECGUARD_BACKUP_RECIPIENT:?Set the age public recipient in /etc/specguard/backup.env}"
mkdir -p /var/backups/specguard
plain_file="$(mktemp /var/backups/specguard/plain.XXXXXXXX.db)"
# The backup command intentionally refuses existing destinations.
rm -- "$plain_file"
trap 'rm -f -- "$plain_file"' EXIT
/opt/specguard/current/.venv/bin/python /opt/specguard/current/scripts/database.py backup \
    /var/lib/specguard/specguard.db "$plain_file"
encrypted="/var/backups/specguard/specguard-$(date -u +%Y%m%dT%H%M%SZ).db.age"
age -r "$SPECGUARD_BACKUP_RECIPIENT" -o "$encrypted" "$plain_file"
find /var/backups/specguard -maxdepth 1 -type f -name 'specguard-*.db.age' -mtime +30 -delete
echo 'Encrypted backup complete. Copy it off the server and verify the copy.'
