#!/bin/bash
# ============================================================
# monday_run.sh — Génération du rapport hebdomadaire (LUNDI)
# Cron : 0 7 * * 1 /root/Projects/morez-events/scripts/monday_run.sh >> /root/Projects/morez-events/data/cron.log 2>&1
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "=============================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] LUNDI — Génération rapport"
echo "=============================================="

cd "$PROJECT_DIR"

# Charger les variables d'environnement
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD}"

# Vérification clé Brave
if [ -z "$BRAVE_API_KEY" ]; then
    echo "[WARN] BRAVE_API_KEY non définie — scraping Brave désactivé"
fi

# Lancement
python3 -m morez_events.cli run --monday

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Terminé avec succès ✓"
