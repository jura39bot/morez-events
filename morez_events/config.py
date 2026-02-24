"""Configuration centrale du projet morez-events."""

import os
from pathlib import Path

# ── Géographie ──────────────────────────────────────────────────────────────
CENTER_CITY = "Morez, Jura"
MAX_DRIVE_MINUTES = 60

# Villes principales pour les requêtes Brave Search (≤1h de Morez)
CITIES = [
    # Jura (39)
    "Morez", "Saint-Claude", "Lons-le-Saunier", "Champagnole",
    "Dole", "Poligny", "Arbois", "Clairvaux-les-Lacs",
    "Saint-Laurent-en-Grandvaux", "Moirans-en-Montagne", "Orgelet",
    # Doubs (25)
    "Pontarlier", "Métabief", "Morteau", "Ornans",
    # Ain (01)
    "Oyonnax", "Nantua", "Bourg-en-Bresse", "Bellegarde-sur-Valserine",
]

# Slugs alentoor.fr pour chaque ville cible (URL: /slug/agenda/cat)
# Toutes les villes sont vérifiées à ≤1h de route depuis Morez (Jura 39)
ALENTOOR_CITY_SLUGS = {
    # ── Jura (39) ────────────────────────────────────────────────────────────
    "Morez":                        "morez",                     # centre, 0 min
    "Prémanon":                     "premanon",                  # 10 min
    "Morbier":                      "morbier",                   # 15 min
    "Lajoux":                       "lajoux",                    # 15 min
    "Bois-d'Amont":                 "bois-d-amont",              # 20 min
    "Longchaumois":                 "longchaumois",              # 20 min
    "Bellefontaine":                "bellefontaine-39",          # 20 min
    "Chaux-des-Prés":               "chaux-des-pres",            # 20 min
    "Viry":                         "viry-39",                   # 20 min
    "Fort-du-Plasne":               "fort-du-plasne",            # 20 min
    "Saint-Claude":                 "saint-claude-39",           # 25 min
    "Mournans-Charbonny":           "mournans-charbonny",        # 25 min
    "Foncine-le-Haut":              "foncine-le-haut",           # 25 min
    "Saint-Lupicin":                "saint-lupicin",             # 25 min
    "La Pesse":                     "la-pesse",                  # 25 min
    "Les Planches-en-Montagne":     "les-planches-en-montagne",  # 25 min
    "Thoiria":                      "thoiria",                   # 25 min
    "Champagnole":                  "champagnole",               # 35 min
    "Moirans-en-Montagne":          "moirans-en-montagne",       # 35 min
    "Clairvaux-les-Lacs":           "clairvaux-les-lacs",        # 35 min
    "Saint-Laurent-en-Grandvaux":   "saint-laurent-en-grandvaux", # 35 min
    "Salins-les-Bains":             "salins-les-bains",          # 35 min
    "Arbois":                       "arbois",                    # 40 min
    "Poligny":                      "poligny",                   # 40 min
    "Orgelet":                      "orgelet",                   # 40 min
    "Arinthod":                     "arinthod",                  # 40 min
    "Beaufort":                     "beaufort-39",               # 40 min
    "Montain":                      "montain-39",                # 40 min
    "Marigny":                      "marigny-39",                # 40 min
    "Mouchard":                     "mouchard",                  # 45 min
    "Lons-le-Saunier":              "lons-le-saunier",           # 45 min
    "Dole":                         "dole",                      # 50 min
    "Plainoiseau":                  "plainoiseau",               # 50 min
    "Commenailles":                 "commenailles",              # 50 min
    "Toulouse-le-Château":          "toulouse-le-chateau",       # 50 min
    "Mont-sous-Vaudrey":            "mont-sous-vaudrey",         # 50 min
    "Cramans":                      "cramans",                   # 50 min
    "Saint-Amour":                  "saint-amour",               # 55 min
    # ── Doubs (25) ───────────────────────────────────────────────────────────
    "Métabief":                     "metabief",                  # 25 min
    "Les Hôpitaux-Neufs":           "les-hopitaux-neufs",        # 25 min
    "Chaux-Neuve":                  "chaux-neuve",               # 25 min
    "Rochejean":                    "rochejean",                 # 25 min
    "Malbuisson":                   "malbuisson",                # 25 min
    "Labergement-Sainte-Marie":     "labergement-sainte-marie",  # 30 min
    "Pontarlier":                   "pontarlier",                # 35 min
    "Montbenoît":                   "montbenoit",                # 35 min
    "Frasne":                       "frasne",                    # 35 min
    "Les Fourgs":                   "les-fourgs",                # 35 min
    "Gilley":                       "gilley-25",                 # 40 min
    "Morteau":                      "morteau",                   # 45 min
    "Grand-Combe-Châteleu":         "grand-combe-chateleu",      # 45 min
    "Ornans":                       "ornans",                    # 50 min
    "Valdahon":                     "valdahon",                  # 50 min
    # ── Ain (01) ─────────────────────────────────────────────────────────────
    "Oyonnax":                      "oyonnax",                   # 35 min
    "Nantua":                       "nantua",                    # 35 min
    "Aranc":                        "aranc",                     # 50 min
    "Izieu":                        "izieu",                     # 50 min
    "Jujurieux":                    "jujurieux",                 # 55 min
    "Culoz":                        "culoz",                     # 55 min
    "Bellegarde-sur-Valserine":     "bellegarde-sur-valserine",  # 45 min
    "Bourg-en-Bresse":              "bourg-en-bresse",           # 55 min
    "Ferney-Voltaire":              "ferney-voltaire",           # 55 min
    "Sauverny":                     "sauverny",                  # 55 min
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
GOG_KEYRING_PASSWORD = os.getenv("GOG_KEYRING_PASSWORD", "")
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
