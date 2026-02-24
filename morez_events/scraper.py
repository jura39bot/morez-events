"""Scraping des événements depuis Brave Search et alentoor.fr (JSON-LD)."""

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from . import config

logger = logging.getLogger(__name__)

# ── Modèle de données ────────────────────────────────────────────────────────

@dataclass
class Event:
    """Représente un événement culturel ou sportif."""
    title: str
    venue: str
    city: str
    date_str: str           # Chaîne date originale (pour affichage)
    date: Optional[date]    # Date parsée (pour filtrage)
    category: str           # concert | culture | sport | autre
    url: str
    source: str             # brave | alentoor
    description: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d

    @staticmethod
    def from_dict(d: dict) -> "Event":
        d = d.copy()
        d["date"] = date.fromisoformat(d["date"]) if d.get("date") else None
        return Event(**d)


def detect_category(text: str) -> str:
    """Détecte la catégorie d'un événement depuis son texte."""
    text_lower = text.lower()
    for cat, keywords in config.CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "autre"


def deduplicate(events: List[Event]) -> List[Event]:
    """Supprime les doublons par (titre normalisé, date, ville)."""
    seen = set()
    unique = []
    for ev in events:
        key = (
            re.sub(r'\s+', ' ', ev.title.lower().strip()),
            ev.date.isoformat() if ev.date else ev.date_str[:10],
            ev.city.lower(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique


# ── Source 1 : Brave Search API ──────────────────────────────────────────────

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

def _brave_query(query: str, count: int = 10) -> List[dict]:
    """Effectue une recherche Brave et retourne les résultats bruts."""
    if not config.BRAVE_API_KEY:
        logger.warning("BRAVE_API_KEY non défini — recherche Brave désactivée")
        return []

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_API_KEY,
    }
    params = {"q": query, "count": count, "country": "fr", "search_lang": "fr"}

    try:
        resp = requests.get(BRAVE_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("web", {}).get("results", [])
    except Exception as e:
        logger.error(f"Erreur Brave Search ({query!r}): {e}")
        return []


def _parse_brave_result(result: dict, city: str) -> Optional[Event]:
    """Convertit un résultat Brave en Event."""
    title = result.get("title", "").strip()
    url = result.get("url", "")
    description = result.get("description", "")

    if not title or not url:
        return None

    parsed_date = None
    date_str = ""
    for fragment in [description, title]:
        try:
            parsed_date = dateparser.parse(fragment, fuzzy=True, dayfirst=True).date()
            date_str = str(parsed_date)
            break
        except Exception:
            pass

    category = detect_category(title + " " + description)

    return Event(
        title=title,
        venue=city,
        city=city,
        date_str=date_str,
        date=parsed_date,
        category=category,
        url=url,
        source="brave",
        description=description[:200],
    )


def search_brave(week_start: date, week_end: date) -> List[Event]:
    """Recherche des événements via Brave Search pour toutes les villes."""
    events = []
    month_year = week_start.strftime("%B %Y")

    queries_templates = [
        "concert {ville} {mois_annee} site:billetweb.fr OR site:fnacspectacles.com OR site:ticketmaster.fr",
        "spectacle théâtre {ville} {mois_annee}",
        "événement sportif match {ville} {mois_annee}",
        "festival exposition {ville} {mois_annee}",
    ]

    for city in config.CITIES:
        for tmpl in queries_templates:
            query = tmpl.format(ville=city, mois_annee=month_year)
            logger.info(f"Brave: {query}")
            results = _brave_query(query, count=5)
            for r in results:
                ev = _parse_brave_result(r, city)
                if ev:
                    events.append(ev)
            time.sleep(0.3)

    return events


# ── Source 2 : alentoor.fr (JSON-LD) ─────────────────────────────────────────

ALENTOOR_BASE = "https://www.alentoor.fr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Catégories à scraper par ville
ALENTOOR_CATS = ["concert", "festival", "spectacle", "theatre", "exposition", "sport", "festivites"]


def _parse_jsonld_event(data: dict, source_dept: str) -> Optional[Event]:
    """Convertit un bloc JSON-LD Event en Event."""
    if data.get("@type") != "Event":
        return None

    title = data.get("name", "").strip()
    url = data.get("url", "") or data.get("@id", "")
    if not title:
        return None

    # Date de début
    start_date_raw = data.get("startDate", "")
    parsed_date = None
    date_str = start_date_raw
    if start_date_raw:
        try:
            # Format peut être "2026-02-25" ou "2026-02-25T20:00:00"
            parsed_date = dateparser.parse(start_date_raw, dayfirst=True).date()
        except Exception:
            pass

    # Lieu
    location = data.get("location", {})
    if isinstance(location, dict):
        venue = location.get("name", "") or location.get("address", "")
        if isinstance(venue, dict):
            venue = venue.get("streetAddress", "")
        # Extraire la ville depuis l'URL (format: /ville/agenda/...)
        city = _extract_city_from_url(url)
    elif isinstance(location, str):
        venue = location
        city = _extract_city_from_url(url)
    else:
        venue = ""
        city = _extract_city_from_url(url)

    # Ville de fallback depuis le département
    if not city:
        city = source_dept.split("-", 1)[-1].title()

    description = data.get("description", "")[:200]
    category = detect_category(title + " " + description)

    return Event(
        title=title,
        venue=str(venue)[:60] if venue else city,
        city=city,
        date_str=date_str,
        date=parsed_date,
        category=category,
        url=url,
        source="alentoor",
        description=description,
    )


def _extract_city_from_url(url: str) -> str:
    """Extrait le nom de la ville depuis une URL alentoor.fr."""
    # Pattern: https://www.alentoor.fr/lons-le-saunier/agenda/...
    match = re.search(r'alentoor\.fr/([^/]+)/agenda', url)
    if match:
        slug = match.group(1)
        # Convertir le slug en nom propre
        city = slug.replace("-", " ").title()
        # Corrections spécifiques
        replacements = {
            "Lons Le Saunier": "Lons-le-Saunier",
            "Bourg En Bresse": "Bourg-en-Bresse",
            "Clairvaux Les Lacs": "Clairvaux-les-Lacs",
        }
        return replacements.get(city, city)
    return ""


def _scrape_alentoor_page(url: str, source_dept: str) -> List[Event]:
    """Scrape une page alentoor.fr et extrait les événements depuis les JSON-LD."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"alentoor.fr: HTTP {resp.status_code} pour {url}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        events = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Peut être un seul objet ou une liste
                items = data if isinstance(data, list) else [data]
                for item in items:
                    ev = _parse_jsonld_event(item, source_dept)
                    if ev:
                        events.append(ev)
            except json.JSONDecodeError:
                continue

        logger.info(f"alentoor.fr: {len(events)} événements depuis {url}")
        return events

    except Exception as e:
        logger.error(f"Erreur scraping {url}: {e}")
        return []


def scrape_alentoor() -> List[Event]:
    """
    Scrape alentoor.fr par ville (JSON-LD).
    Utilise les slugs de ville configurés dans config.ALENTOOR_CITY_SLUGS
    pour ne récupérer que les événements dans le rayon ≤1h de Morez.
    """
    events = []

    for city_name, city_slug in config.ALENTOOR_CITY_SLUGS.items():
        # Page principale de la ville (tous types)
        url_main = f"{ALENTOOR_BASE}/{city_slug}/agenda"
        page_events = _scrape_alentoor_page(url_main, city_slug)
        # Forcer le nom de ville propre
        for ev in page_events:
            if not ev.city or ev.city.lower() == city_slug:
                ev.city = city_name
        events.extend(page_events)
        time.sleep(0.8)

        # Pages par catégorie pour plus de résultats
        for cat_slug in ALENTOOR_CATS:
            url = f"{ALENTOOR_BASE}/{city_slug}/agenda/{cat_slug}"
            page_events = _scrape_alentoor_page(url, city_slug)
            for ev in page_events:
                if not ev.city or ev.city.lower() == city_slug:
                    ev.city = city_name
            events.extend(page_events)
            time.sleep(0.5)

    return events


# ── Collecte principale ───────────────────────────────────────────────────────

def collect_events(week_start: date, week_end: date) -> List[Event]:
    """
    Collecte tous les événements depuis les deux sources,
    filtre sur la semaine et déduplique.
    """
    logger.info(f"Collecte événements du {week_start} au {week_end}")

    all_events: List[Event] = []

    # Source 1 : Brave Search (si clé disponible)
    try:
        brave_events = search_brave(week_start, week_end)
        logger.info(f"Brave: {len(brave_events)} événements bruts")
        all_events.extend(brave_events)
    except Exception as e:
        logger.error(f"Erreur source Brave: {e}")

    # Source 2 : alentoor.fr (JSON-LD, pas de clé requise)
    try:
        alentoor_events = scrape_alentoor()
        logger.info(f"alentoor.fr: {len(alentoor_events)} événements bruts")
        all_events.extend(alentoor_events)
    except Exception as e:
        logger.error(f"Erreur source alentoor.fr: {e}")

    # Filtrage sur la semaine
    filtered = []
    for ev in all_events:
        if ev.date is None or (week_start <= ev.date <= week_end):
            filtered.append(ev)

    # Dédoublonnage
    unique = deduplicate(filtered)
    logger.info(f"Total après filtrage + déduplication: {len(unique)} événements")

    return unique
