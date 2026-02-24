"""Scraping des événements depuis Brave Search et sortir.eu."""

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
    date_str: str          # Chaîne date originale (pour affichage)
    date: Optional[date]   # Date parsée (pour filtrage)
    category: str          # concert | culture | sport | autre
    url: str
    source: str            # brave | sortirieu
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

    # Essayer d'extraire une date depuis la description
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
    venue = city  # Brave ne donne pas de salle précise en général

    return Event(
        title=title,
        venue=venue,
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
        "concert {ville} {mois_annee} site:sortir.eu OR site:fnacspectacles.com OR site:billetweb.fr",
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
            time.sleep(0.3)  # Politesse envers l'API

    return events


# ── Source 2 : Scraping sortir.eu ────────────────────────────────────────────

SORTIRIEU_BASE = "https://www.sortir.eu"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def _parse_sortirieu_page(html: str, city: str, base_url: str) -> List[Event]:
    """Parse une page sortir.eu et extrait les événements."""
    events = []
    soup = BeautifulSoup(html, "lxml")

    # sortir.eu utilise des cards avec classe "event-item" ou similaire
    # On cherche les blocs d'événements de manière générique
    selectors = [
        "article.event",
        ".event-item",
        ".agenda-item",
        "li.event",
        ".card-event",
        "article[class*='event']",
        "div[class*='event-card']",
    ]

    items = []
    for sel in selectors:
        items = soup.select(sel)
        if items:
            logger.info(f"sortir.eu {city}: {len(items)} items avec sélecteur '{sel}'")
            break

    if not items:
        # Fallback : chercher tous les liens qui ressemblent à des événements
        items = soup.find_all("a", href=re.compile(r"/agenda/|/event/|/spectacle/"))
        logger.info(f"sortir.eu {city}: {len(items)} liens fallback")

    for item in items[:20]:  # Limiter à 20 par page
        try:
            # Titre
            title_el = (
                item.find(["h2", "h3", "h4"])
                or item.find(class_=re.compile(r"title|name"))
                or (item if item.name == "a" else None)
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 4:
                continue

            # URL
            link_el = item.find("a") or (item if item.name == "a" else None)
            url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                url = href if href.startswith("http") else SORTIRIEU_BASE + href

            # Date
            date_el = item.find(["time", "span"], class_=re.compile(r"date|time|when"))
            date_str = date_el.get_text(strip=True) if date_el else ""
            if not date_str and item.find("time"):
                date_str = item.find("time").get("datetime", "")

            parsed_date = None
            if date_str:
                try:
                    parsed_date = dateparser.parse(date_str, fuzzy=True, dayfirst=True).date()
                except Exception:
                    pass

            # Lieu
            venue_el = item.find(class_=re.compile(r"venue|lieu|place|salle"))
            venue = venue_el.get_text(strip=True) if venue_el else city

            category = detect_category(title)

            events.append(Event(
                title=title,
                venue=venue or city,
                city=city,
                date_str=date_str,
                date=parsed_date,
                category=category,
                url=url,
                source="sortirieu",
            ))
        except Exception as e:
            logger.debug(f"Erreur parsing item sortir.eu: {e}")
            continue

    return events


def scrape_sortirieu() -> List[Event]:
    """Scrape sortir.eu pour toutes les villes configurées."""
    events = []

    for city, slug in config.SORTIRIEU_SLUGS.items():
        url = f"{SORTIRIEU_BASE}/{slug}/agenda/"
        logger.info(f"Scraping sortir.eu: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"sortir.eu {city}: HTTP {resp.status_code}")
                continue
            page_events = _parse_sortirieu_page(resp.text, city, url)
            logger.info(f"sortir.eu {city}: {len(page_events)} événements trouvés")
            events.extend(page_events)
            time.sleep(1)  # Politesse envers le serveur
        except Exception as e:
            logger.error(f"Erreur sortir.eu {city}: {e}")

    return events


# ── Collecte principale ───────────────────────────────────────────────────────

def collect_events(week_start: date, week_end: date) -> List[Event]:
    """
    Collecte tous les événements depuis les deux sources,
    filtre sur la semaine et déduplique.
    """
    logger.info(f"Collecte événements du {week_start} au {week_end}")

    all_events: List[Event] = []

    # Source 1 : Brave Search
    try:
        brave_events = search_brave(week_start, week_end)
        logger.info(f"Brave: {len(brave_events)} événements bruts")
        all_events.extend(brave_events)
    except Exception as e:
        logger.error(f"Erreur source Brave: {e}")

    # Source 2 : sortir.eu
    try:
        sortir_events = scrape_sortirieu()
        logger.info(f"sortir.eu: {len(sortir_events)} événements bruts")
        all_events.extend(sortir_events)
    except Exception as e:
        logger.error(f"Erreur source sortir.eu: {e}")

    # Filtrage sur la semaine (événements avec date connue dans la plage)
    # Garder aussi les événements sans date (date=None) pour ne rien rater
    filtered = []
    for ev in all_events:
        if ev.date is None or (week_start <= ev.date <= week_end):
            filtered.append(ev)

    # Dédoublonnage
    unique = deduplicate(filtered)
    logger.info(f"Total après filtrage + déduplication: {len(unique)} événements")

    return unique
