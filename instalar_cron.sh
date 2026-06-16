#!/bin/bash
# Instala (o reinstala) el cron que corre el scraper cada 5 minutos.
set -e

DIR="$HOME/mundial-scraper"
PY="$(command -v python3)"
LINE="*/5 * * * * cd $DIR && $PY scraper.py >> $DIR/data/cron.log 2>&1"
TAG="# mundial-scraper"

# Quita cualquier linea previa del scraper y agrega la nueva.
( crontab -l 2>/dev/null | grep -v "$TAG" ; echo "$LINE $TAG" ) | crontab -

echo "Cron instalado:"
crontab -l | grep "$TAG"
