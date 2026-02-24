"""Configuration centrale du projet morez-events."""

import os
from pathlib import Path

# ── Géographie ──────────────────────────────────────────────────────────────
CENTER_CITY = "Morez, Jura"
MAX_DRIVE_MINUTES = 60

# Villes à couvrir (≤1h de Morez par route)
CITIES = [
    "Morez",
    "Saint-Claude",
    "Lons-le-Saunier",
    "Champagnole",
    "Pontarlier",
    "Oyonnax",
    "Bourg-en-Bresse",
    "Dole",
    "Poligny",
    "Clairvaux-les-Lacs",
]

# Slugs alentoor.fr pour chaque ville cible (URL: /slug/agenda/cat)
ALENTOOR_CITY_SLUGS = {
    # Jura (39)
    "Morez":                   "morez",
    "Saint-Claude":            "saint-claude-39",
    "Lons-le-Saunier":         "lons-le-saunier",
    "Champagnole":             "champagnole",
    "Poligny":                 "poligny",
    "Dole":                    "dole",
    "Clairvaux-les-Lacs":      "clairvaux-les-lacs",
    "Arbois":                  "arbois",          # inclus car proche et intéressant
    "Saint-Laurent-en-Grandvaux": "saint-laurent-en-grandvaux",
    "Orgelet":                 "orgelet",
    "Moirans-en-Montagne":     "moirans-en-montagne",
    # Doubs (25) — uniquement villes ≤1h
    "Pontarlier":              "pontarlier",
    # Ain (01) — uniquement villes ≤1h
    "Oyonnax":                 "oyonnax",
    "Bourg-en-Bresse":         "bourg-en-bresse",
}

# ── Chemins ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
REPORT_PATH = DATA_DIR / "weekly_report.md"
EVENTS_CACHE = DATA_DIR / "events_cache.json"
LOG_PATH = DATA_DIR / "cron.log"

# ── Email ────────────────────────────────────────────────────────────────────
EMAIL_FROM = "jura39bot@gmail.com"
EMAIL_TO = "chetam70@gmail.com"

# ── Credentials (depuis variables d'environnement ou valeurs par défaut) ─────
GOG_KEYRING_PASSWORD = os.getenv("GOG_KEYRING_PASSWORD", "***REMOVED***")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# ── Catégories d'événements ──────────────────────────────────────────────────
CATEGORIES = {
    "concert": "🎵 Concerts & Musique",
    "culture": "🎭 Culture & Spectacles",
    "sport": "⚽ Sports",
    "autre": "🎪 Autres événements",
}

# Mots-clés pour détecter la catégorie depuis le titre/description
CATEGORY_KEYWORDS = {
    "concert": [
        "concert", "musique", "live", "festival", "rock", "jazz", "blues",
        "classique", "opéra", "chanson", "rap", "electro", "métal", "folk",
    ],
    "sport": [
        "match", "tournoi", "compétition", "football", "rugby", "basketball",
        "handball", "tennis", "trail", "course", "vélo", "cyclisme", "ski",
        "natation", "athlétisme", "volley", "hockey",
    ],
    "culture": [
        "théâtre", "exposition", "cinéma", "spectacle", "danse", "ballet",
        "cirque", "humour", "stand-up", "conférence", "lecture", "librairie",
        "musée", "vernissage", "comédie", "pièce", "marionnette",
    ],
}
