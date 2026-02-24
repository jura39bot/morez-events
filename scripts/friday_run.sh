#!/bin/bash
# ============================================================
# friday_run.sh — Mise à jour + envoi email (VENDREDI)
# Cron : 0 17 * * 5 /root/Projects/morez-events/scripts/friday_run.sh >> /root/Projects/morez-events/data/cron.log 2>&1
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "=============================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] VENDREDI — Mise à jour + email"
echo "=============================================="

cd "$PROJECT_DIR"

# Charger les variables d'environnement
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-***REMOVED***}"

# Vérification clé Brave
if [ -z "$BRAVE_API_KEY" ]; then
    echo "[WARN] BRAVE_API_KEY non définie — scraping Brave désactivé"
fi

# Lancement mise à jour + email
python3 -m morez_events run --friday

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Terminé avec succès ✓"
