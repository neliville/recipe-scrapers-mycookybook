#!/usr/bin/env bash
#
# deploy-staging.sh — Déploiement automatique staging o2switch
# Exécuté sur le serveur via GitHub Actions (SSH) ou manuellement.
#
set -e

APP_DIR="/home/iwob6566/apps/recipe-scrapers-mycookybook"
VENV="/home/iwob6566/virtualenv/apps/recipe-scrapers-mycookybook/3.11/bin/activate"

echo "=== DEPLOY STAGING — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

cd "$APP_DIR"

echo "Branche courante : $(git branch --show-current)"
echo "Commit courant   : $(git rev-parse --short HEAD)"

git fetch origin
git checkout develop
git pull origin develop

echo "Branche après pull : $(git branch --show-current)"
echo "Commit après pull  : $(git rev-parse --short HEAD)"

source "$VENV"

python -m pip install --upgrade pip
pip install -r mycookybook_api/requirements.txt
pip install -e .

python -c "from recipe_scrapers import scrape_me; print('recipe_scrapers OK')"
python -c "from mycookybook_api.app import app; print('flask OK')"

mkdir -p tmp
touch tmp/restart.txt

echo "DEPLOY SUCCESS"
