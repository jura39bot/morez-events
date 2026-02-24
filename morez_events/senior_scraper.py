"""
Scraping des activités seniors depuis les sites CCAS/mairies des villes cibles.
Utilise Brave Search pour cibler les pages officielles, puis extrait les données.
"""

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from . import config
from .scraper import Event, detect_category, _brave_query, _parse_brave_result

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Requêtes Brave Search ciblées CCAS/mairies ───────────────────────────────

SENIOR_QUERY_TEMPLATES = [
    # Requêtes ciblant CCAS et mairies officielles
    "CCAS {ville} activités seniors programme agenda 2026",
    "mairie {ville} seniors animations ateliers 2026",
    "club seniors {ville} programme activités",
    "gym douce atelier mémoire qi-gong {ville} 2026",
    "{ville} CCAS seniors atelier sortie gym 2026",
]

# Sites connus pour les activités seniors dans la région
TRUSTED_SENIOR_DOMAINS = [
    "morez.fr", "morbier.fr", "les-rousses.com", "premanon.fr",
    "boisd-amont.com", "saint-claude.fr", "champagnole.fr",
    "boisdamont.fr", "leroussesvillagejurassien.fr",
]

# Mots-clés négatifs (à exclure si dans le titre)
NEGATIVE_KEYWORDS = [
    "recrutement", "emploi", "offre d'emploi", "appel d'offre",
    "marché public", "budget", "délibération", "conseil municipal",
    "immobilier", "vente", "location",
]


def _is_senior_relevant(text: str) -> bool:
    """Vérifie si un texte est pertinent pour les activités seniors."""
    text_lower = text.lower()
    # Doit contenir au moins un mot-clé senior
    has_senior_kw = any(kw in text_lower for kw in config.CATEGORY_KEYWORDS["senior"])
    # Ne doit pas contenir de mots-clés négatifs
    has_negative = any(kw in text_lower for kw in NEGATIVE_KEYWORDS)
    return has_senior_kw and not has_negative


def _parse_date_from_text(text: str, week_start: date, week_end: date) -> Optional[date]:
    """
    Tente d'extraire une date du texte.
    Si aucune date trouvée, retourne None (l'événement sera inclus quand même
    car les activités seniors sont souvent hebdomadaires sans date précise).
    """
    # Patterns dates françaises
    patterns = [
        r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b',        # 25/02/2026
        r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|'
        r'juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',  # 25 février 2026
        r'\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+'
        r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|'
        r'juillet|août|septembre|octobre|novembre|décembre)\b',   # lundi 25 février
    ]

    mois_fr = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    }

    text_lower = text.lower()

    # Pattern numérique
    m = re.search(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b', text_lower)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # Pattern "25 février 2026"
    m = re.search(
        r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|'
        r'juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',
        text_lower
    )
    if m:
        try:
            mois = mois_fr[m.group(2)]
            return date(int(m.group(3)), mois, int(m.group(1)))
        except (ValueError, KeyError):
            pass

    # Pattern "lundi 25 février"
    m = re.search(
        r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+'
        r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|'
        r'juillet|août|septembre|octobre|novembre|décembre)\b',
        text_lower
    )
    if m:
        try:
            mois = mois_fr[m.group(2)]
            year = week_start.year
            return date(year, mois, int(m.group(1)))
        except (ValueError, KeyError):
            pass

    # Fallback dateutil
    try:
        parsed = dateparser.parse(text[:200], fuzzy=True, dayfirst=True)
        if parsed:
            d = parsed.date()
            # Accepter seulement si dans une plage raisonnable (±3 mois)
            if week_start - timedelta(days=90) <= d <= week_end + timedelta(days=90):
                return d
    except Exception:
        pass

    return None


def _extract_events_from_soup(
    soup: BeautifulSoup, url: str, city: str, week_start: date, week_end: date
) -> List[Event]:
    """Extrait les activités seniors depuis un BeautifulSoup parsé."""
    events = []
    from urllib.parse import urlparse

    # Supprimer nav/footer/aside pour ne garder que le contenu principal
    for tag in soup.find_all(["nav", "footer", "aside", "header"]):
        tag.decompose()

    candidates = []

    # Stratégie 1 : éléments <article> ou <li> ou <div> avec contenu senior
    for el in soup.find_all(["article", "li", "div"], limit=200):
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 30 or len(text) > 2000:
            continue
        if _is_senior_relevant(text):
            candidates.append((el, text))

    # Stratégie 2 : fallback sur paragraphes contenant des mots-clés
    if not candidates:
        for el in soup.find_all(["p", "h2", "h3", "h4"], limit=300):
            text = el.get_text(separator=" ", strip=True)
            if _is_senior_relevant(text):
                candidates.append((el, text))

    seen_titles = set()
    for el, text in candidates[:20]:
        title_el = el.find(["h1", "h2", "h3", "h4", "strong", "b"])
        if title_el:
            title = title_el.get_text(strip=True)[:80]
        else:
            title = text[:60].split(".")[0].strip()

        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        # Exclure les fils d'Ariane (breadcrumbs) : contiennent "/"
        if title.count("/") >= 2 or title.startswith("Accueil"):
            continue

        # Exclure les titres trop génériques
        if title.lower() in {"action sociale – ccas", "ccas", "social", "seniors", "mairie"}:
            continue

        if any(kw in title.lower() for kw in NEGATIVE_KEYWORDS):
            continue

        ev_date = _parse_date_from_text(text, week_start, week_end)

        link_el = el.find("a", href=True)
        ev_url = url
        if link_el:
            href = link_el["href"]
            if href.startswith("http"):
                ev_url = href
            elif href.startswith("/"):
                parsed_url = urlparse(url)
                ev_url = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"

        events.append(Event(
            title=title,
            venue=city,
            city=city,
            date_str=ev_date.isoformat() if ev_date else "récurrent",
            date=ev_date,
            category="senior",
            url=ev_url,
            source="ccas",
            description=text[:200],
        ))

    return events


def _scrape_ccas_page(url: str, city: str, week_start: date, week_end: date) -> List[Event]:
    """
    Scrape une page CCAS/mairie pour extraire les activités seniors.
    Suit également les liens internes vers des sous-pages senior (1 niveau).
    """
    from urllib.parse import urlparse

    events = []
    visited = {url}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.debug(f"CCAS {city}: HTTP {resp.status_code} → {url}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Extraire les events de la page principale
        page_events = _extract_events_from_soup(soup, url, city, week_start, week_end)
        events.extend(page_events)

        # Chercher les liens internes vers des sous-pages senior (1 niveau)
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        senior_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            link_text = a.get_text(strip=True).lower()

            # Liens internes uniquement
            if href.startswith("/"):
                full_url = base_domain + href
            elif href.startswith(base_domain):
                full_url = href
            else:
                continue

            if full_url in visited:
                continue

            # Le lien doit pointer vers quelque chose de senior
            combined = href.lower() + " " + link_text
            if any(kw in combined for kw in [
                "senior", "aîné", "retraite", "bien-etre", "bien_etre",
                "social", "ccas", "atelier", "animation", "activite", "gym"
            ]):
                senior_links.append(full_url)

        # Scraper jusqu'à 4 sous-pages senior
        for sub_url in senior_links[:4]:
            visited.add(sub_url)
            try:
                sub_resp = requests.get(sub_url, headers=HEADERS, timeout=12)
                if sub_resp.status_code == 200:
                    sub_soup = BeautifulSoup(sub_resp.text, "lxml")
                    sub_events = _extract_events_from_soup(sub_soup, sub_url, city, week_start, week_end)
                    events.extend(sub_events)
                    time.sleep(0.4)
            except Exception:
                pass

        if events:
            logger.info(f"CCAS {city}: {len(events)} activités trouvées depuis {url}")

    except Exception as e:
        logger.debug(f"CCAS {city}: erreur scraping {url}: {e}")

    return events


def search_senior_brave(city: str, week_start: date, week_end: date) -> List[Event]:
    """
    Effectue des recherches Brave Search ciblées pour les activités seniors
    d'une ville donnée, visant les sites CCAS et mairies.
    """
    events = []
    month_year = week_start.strftime("%B %Y")
    scraped_urls = set()

    for tmpl in SENIOR_QUERY_TEMPLATES:
        query = tmpl.format(ville=city, mois_annee=month_year)
        logger.info(f"Senior Brave [{city}]: {query}")

        results = _brave_query(query, count=8)
        time.sleep(0.4)

        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            description = r.get("description", "")
            combined = f"{title} {description}"

            # Vérifier pertinence senior
            if not _is_senior_relevant(combined):
                # Inclure quand même si domaine trusted (CCAS officiel)
                domain_ok = any(d in url for d in TRUSTED_SENIOR_DOMAINS)
                if not domain_ok:
                    continue

            # Scraper la page si pas encore vue
            if url and url not in scraped_urls:
                scraped_urls.add(url)
                page_events = _scrape_ccas_page(url, city, week_start, week_end)
                if page_events:
                    events.extend(page_events)
                    time.sleep(0.6)
                else:
                    # Fallback : créer un event depuis le résultat Brave directement
                    ev = _parse_brave_result(r, city)
                    if ev and _is_senior_relevant(combined):
                        ev.category = "senior"
                        ev.source = "brave-senior"
                        events.append(ev)

    return events


def collect_senior_events(week_start: date, week_end: date) -> List[Event]:
    """
    Collecte les activités seniors pour toutes les villes cibles.
    Point d'entrée appelé depuis scraper.collect_events().
    """
    all_senior: List[Event] = []

    logger.info(f"Senior: collecte pour {len(config.SENIOR_CITIES)} villes cibles")

    for city in config.SENIOR_CITIES:
        logger.info(f"Senior: traitement de {city}")
        city_events = search_senior_brave(city, week_start, week_end)
        logger.info(f"Senior [{city}]: {len(city_events)} activités")
        all_senior.extend(city_events)
        time.sleep(1.0)  # Politesse entre villes

    # Filtrer les events dans la semaine (ou sans date = récurrents inclus)
    filtered = []
    for ev in all_senior:
        if ev.date is None:
            # Activité récurrente sans date précise → inclure si contenu pertinent
            filtered.append(ev)
        elif week_start <= ev.date <= week_end:
            filtered.append(ev)

    logger.info(f"Senior: {len(filtered)} activités après filtrage sur la semaine")
    return filtered
