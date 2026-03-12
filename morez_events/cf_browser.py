"""
Remplacement de requests.get() par Cloudflare Browser Rendering.
Rend les pages JS-dynamiques et contourne les protections anti-bots.
Fallback automatique sur requests si CF indisponible ou quota dépassé.
"""

import json
import logging
import time
import urllib.request
import urllib.error

import requests

from . import config

logger = logging.getLogger(__name__)

CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}/browser-rendering"
CF_HEADERS = {
    "Authorization": f"Bearer {config.CF_API_TOKEN}",
    "Content-Type": "application/json",
}

# Délai entre requêtes CF (rate limit : ~1 req/s)
CF_DELAY = 1.5

# Nombre de retries sur 429
CF_MAX_RETRIES = 2


class FetchResult:
    """Simule une réponse requests.Response pour compatibilité avec le code existant."""
    def __init__(self, text: str, status_code: int, url: str):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _cf_fetch_html(url: str) -> str | None:
    """
    Récupère le HTML rendu d'une page via Cloudflare /content (headless browser).
    Retourne le HTML ou None en cas d'échec.
    """
    if not config.CF_ACCOUNT_ID or not config.CF_API_TOKEN:
        return None

    payload = json.dumps({
        "url": url,
        "gotoOptions": {
            "waitUntil": "networkidle2",
            "timeout": 30000,
        },
        "rejectResourceTypes": ["image", "media", "font"],
    }).encode("utf-8")

    for attempt in range(CF_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                f"{CF_BASE}/content",
                data=payload,
                headers=CF_HEADERS,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read())
                result = data.get("result", "")
                if isinstance(result, str) and len(result) > 200:
                    logger.debug(f"CF /content OK: {url} ({len(result)} chars)")
                    return result
                return None

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 3 * (attempt + 1)
                logger.debug(f"CF rate limit pour {url}, attente {wait}s")
                time.sleep(wait)
                continue
            logger.debug(f"CF /content HTTP {e.code} pour {url}")
            return None
        except Exception as e:
            logger.debug(f"CF /content erreur pour {url}: {e}")
            return None

    return None


def fetch_page(url: str, timeout: int = 15, use_cf: bool = True) -> FetchResult:
    """
    Récupère une page web avec fallback :
    1. Cloudflare Browser Rendering (JS rendu, anti-bot contourné)
    2. requests classique (si CF indisponible ou désactivé)

    Compatible avec l'interface requests.Response (attributs .text, .status_code).
    """
    # Essai Cloudflare en premier
    if use_cf and config.CF_ACCOUNT_ID and config.CF_API_TOKEN:
        html = _cf_fetch_html(url)
        if html:
            time.sleep(CF_DELAY)
            return FetchResult(text=html, status_code=200, url=url)
        logger.debug(f"CF indisponible pour {url}, fallback requests")

    # Fallback requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        return FetchResult(text=resp.text, status_code=resp.status_code, url=url)
    except Exception as e:
        logger.warning(f"Fallback requests aussi échoué pour {url}: {e}")
        return FetchResult(text="", status_code=0, url=url)
