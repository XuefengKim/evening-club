#!/bin/bash
set -euo pipefail
dest=/opt/evening-club/backups
tar -czf "$dest/data-$(date -u +%Y%m%dT%H%M%SZ).tgz" -C /opt/evening-club/shared data
find "$dest" -name 'data-*.tgz' -mtime +14 -delete
