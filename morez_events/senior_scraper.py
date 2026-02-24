"""Scraping des activités seniors pour les villes cibles."""

import logging
import re
import time
from datetime import date
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from . import config
from .scraper import Event, detect_category

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


# ── Brave Search — requêtes spécifiques seniors ──────────────────────────────

SENIOR_QUERIES = [
    "activités seniors {ville} {mois_annee}",
    "gym douce yoga seniors {ville} {mois_annee}",
    "club seniors CCAS {ville} agenda {mois_annee}",
    "atelier mémoire qi-gong retraités {ville} {mois_annee}",
    "animations seniors {ville} {annee}",
]

# URLs CCAS et mairies connues pour les villes senior ciblées
CCAS_URLS = {
    "Morez":       "https://www.morez.fr/",
    "Saint-Claude": "https://www.ville-saint-claude.fr/",
    "Champagnole": "https://www.champagnole.fr/mairie-et-services/social/ateliers-collectifs-seniors-20212022/",
    "Morbier":     "https://www.morbier.fr/",
    "Les Rousses": "https://www.lesrousses.com/",
    "Prémanon":    "https://www.premanon.fr/",
    "Bois-d'Amont": "https://www.boisd-amont.fr/",
}


def _brave_query(query: str, count: int = 5) -> List[dict]:
    """Effectue une recherche Brave et retourne les résultats bruts."""
    if not config.BRAVE_API_KEY:
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
        logger.error(f"Brave senior ({query!r}): {e}")
        return []


def _parse_brave_senior(result: dict, city: str) -> Optional[Event]:
    """Convertit un résultat Brave en Event senior."""
    title = result.get("title", "").strip()
    url = result.get("url", "")
    description = result.get("description", "")
    if not title or not url:
        return None

    # Essayer de parser une date
    parsed_date = None
    date_str = ""
    for fragment in [description, title]:
        try:
            parsed_date = dateparser.parse(fragment, fuzzy=True, dayfirst=True).date()
            date_str = str(parsed_date)
            break
        except Exception:
            pass

    return Event(
        title=title,
        venue=city,
        city=city,
        date_str=date_str,
        date=parsed_date,
        category="senior",
        url=url,
        source="brave-senior",
        description=description[:200],
    )


def search_brave_senior(week_start: date, week_end: date) -> List[Event]:
    """Recherche d'activités seniors via Brave Search pour les villes cibles."""
    events = []
    month_year = week_start.strftime("%B %Y")
    year = str(week_start.year)

    for city in config.SENIOR_CITIES:
        for tmpl in SENIOR_QUERIES:
            query = tmpl.format(ville=city, mois_annee=month_year, annee=year)
            logger.info(f"Brave senior: {query}")
            results = _brave_query(query, count=5)
            for r in results:
                ev = _parse_brave_senior(r, city)
                if ev:
                    events.append(ev)
            time.sleep(0.3)

    logger.info(f"Brave senior: {len(events)} événements bruts")
    return events


# ── Scraping CCAS et mairies ─────────────────────────────────────────────────

def _parse_senior_page(html: str, city: str, url: str) -> List[Event]:
    """Extrait les activités seniors depuis une page mairie/CCAS."""
    events = []
    soup = BeautifulSoup(html, "lxml")

    # Mots-clés senior dans le texte
    senior_keywords = [
        "senior", "retraité", "âge d'or", "gym douce", "qi-gong", "qigong",
        "atelier mémoire", "sophrologie", "tai chi", "yoga", "marche nordique",
        "animation senior", "club senior", "ccas",
    ]

    # Chercher les blocs/sections qui parlent de seniors
    for tag in soup.find_all(["article", "div", "li", "section", "p"], limit=200):
        text = tag.get_text(" ", strip=True).lower()
        if not any(kw in text for kw in senior_keywords):
            continue
        if len(text) < 20 or len(text) > 1000:
            continue

        # Extraire le titre
        title_el = tag.find(["h1", "h2", "h3", "h4", "strong", "b"])
        title = title_el.get_text(strip=True) if title_el else tag.get_text(strip=True)[:80]
        title = re.sub(r'\s+', ' ', title).strip()
        if not title or len(title) < 5:
            continue

        # Date
        parsed_date = None
        date_str = ""
        time_el = tag.find("time")
        if time_el:
            date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
            try:
                parsed_date = dateparser.parse(date_str, fuzzy=True, dayfirst=True).date()
            except Exception:
                pass

        # Lien
        link_el = tag.find("a")
        ev_url = url
        if link_el and link_el.get("href"):
            href = link_el["href"]
            ev_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")

        events.append(Event(
            title=title[:80],
            venue=city,
            city=city,
            date_str=date_str,
            date=parsed_date,
            category="senior",
            url=ev_url,
            source="mairie",
            description=tag.get_text(" ", strip=True)[:200],
        ))

    # Dédupliquer par titre
    seen = set()
    unique = []
    for ev in events:
        key = ev.title.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return unique


def scrape_ccas_mairies() -> List[Event]:
    """Scrape les pages CCAS/mairies des villes senior cibles."""
    events = []

    for city, url in CCAS_URLS.items():
        logger.info(f"Scraping mairie/CCAS: {city} — {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                logger.warning(f"  HTTP {resp.status_code} pour {url}")
                continue
            page_events = _parse_senior_page(resp.text, city, url)
            logger.info(f"  {len(page_events)} activités senior trouvées")
            events.extend(page_events)
            time.sleep(1)
        except Exception as e:
            logger.error(f"  Erreur {city}: {e}")

    return events


# ── Collecte senior principale ────────────────────────────────────────────────

def collect_senior_events(week_start: date, week_end: date) -> List[Event]:
    """
    Collecte toutes les activités seniors :
    - Brave Search ciblé senior (villes cibles)
    - Scraping CCAS/mairies
    Retourne les events avec category='senior', filtrés sur la semaine.
    """
    all_events = []

    # Source 1 : Brave Search senior
    try:
        all_events.extend(search_brave_senior(week_start, week_end))
    except Exception as e:
        logger.error(f"Erreur Brave senior: {e}")

    # Source 2 : CCAS/mairies
    try:
        all_events.extend(scrape_ccas_mairies())
    except Exception as e:
        logger.error(f"Erreur CCAS: {e}")

    # Filtre sur semaine (garder aussi sans date)
    filtered = [
        ev for ev in all_events
        if ev.date is None or (week_start <= ev.date <= week_end)
    ]

    # Dédoublonnage
    seen = set()
    unique = []
    for ev in filtered:
        key = (re.sub(r'\s+', ' ', ev.title.lower().strip()), ev.city.lower())
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    logger.info(f"Senior: {len(unique)} activités après filtrage")
    return unique
