"""Synchronisation des événements vers Google Calendar via gog CLI."""

import json
import logging
import os
import subprocess
from datetime import date, datetime, timedelta
from typing import List, Optional

from . import config
from .scraper import Event

logger = logging.getLogger(__name__)

CALENDAR_ID = "jura39bot@gmail.com"
# Tag pour retrouver les événements créés par morez-events (évite les doublons)
MOREZ_TAG = "[morez-events]"


def _gog_env() -> dict:
    """Variables d'environnement pour gog."""
    env = os.environ.copy()
    env["GOG_KEYRING_PASSWORD"] = config.GOG_KEYRING_PASSWORD
    return env


def _run_gog(args: list, dry_run: bool = False) -> Optional[str]:
    """Exécute une commande gog et retourne la sortie."""
    cmd = ["gog", "calendar"] + args + ["--account", CALENDAR_ID, "--json"]
    if dry_run:
        logger.info(f"[DRY RUN] {' '.join(cmd)}")
        return None
    try:
        result = subprocess.run(cmd, env=_gog_env(), capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"gog erreur: {e.stderr.strip()}")
        return None


def _existing_morez_events(week_start: date, week_end: date) -> set:
    """
    Récupère les IDs des événements morez-events déjà dans le calendar.
    """
    try:
        cmd = [
            "gog", "calendar", "events", CALENDAR_ID,
            "--account", CALENDAR_ID,
            "--from", week_start.isoformat(),
            "--to", week_end.isoformat(),
            "--json",
        ]
        result = subprocess.run(
            cmd, env=_gog_env(), capture_output=True, text=True,
            check=True, timeout=30
        )
        data = json.loads(result.stdout or "[]")
        if isinstance(data, list):
            ids = set()
            for ev in data:
                desc = ev.get("description", "") or ""
                summary = ev.get("summary", "") or ""
                if MOREZ_TAG in desc or MOREZ_TAG in summary:
                    ids.add(ev.get("id", ""))
            logger.info(f"Calendar: {len(ids)} événements morez-events existants cette semaine")
            return ids
        return set()
    except Exception as e:
        logger.warning(f"Impossible de récupérer les events existants: {e}")
        return set()


def _event_key(ev: Event) -> str:
    """Clé unique pour identifier un événement (déduplication)."""
    import re
    title = re.sub(r'\s+', ' ', ev.title.lower().strip())
    d = ev.date.isoformat() if ev.date else "nodate"
    city = ev.city.lower()
    return f"{title}|{d}|{city}"


def _delete_morez_events(week_start: date, week_end: date) -> int:
    """Supprime les événements morez-events existants pour la semaine (pour mise à jour)."""
    deleted = 0
    try:
        from_str = f"{week_start.isoformat()}T00:00:00+01:00"
        to_str = f"{week_end.isoformat()}T23:59:59+01:00"
        cmd = [
            "gog", "calendar", "events", CALENDAR_ID,
            "--account", CALENDAR_ID,
            "--from", week_start.isoformat(),
            "--to", week_end.isoformat(),
            "--json",
        ]
        result = subprocess.run(
            cmd, env=_gog_env(), capture_output=True, text=True,
            check=True, timeout=30
        )
        data = json.loads(result.stdout or "[]")
        if not isinstance(data, list):
            return 0

        for ev in data:
            desc = ev.get("description", "") or ""
            summary = ev.get("summary", "") or ""
            if MOREZ_TAG in desc or MOREZ_TAG in summary:
                event_id = ev.get("id", "")
                if event_id:
                    del_cmd = [
                        "gog", "calendar", "delete", CALENDAR_ID, event_id,
                        "--account", CALENDAR_ID, "--force",
                    ]
                    try:
                        subprocess.run(
                            del_cmd, env=_gog_env(),
                            capture_output=True, check=True, timeout=15
                        )
                        deleted += 1
                    except Exception as e:
                        logger.debug(f"Erreur suppression {event_id}: {e}")
    except Exception as e:
        logger.warning(f"Erreur suppression events: {e}")
    logger.info(f"Calendar: {deleted} événements supprimés pour mise à jour")
    return deleted


def push_events_to_calendar(
    events: List[Event],
    week_start: date,
    week_end: date,
    update_mode: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Pousse les événements vers Google Calendar.

    Args:
        events: Liste des événements à créer.
        week_start / week_end: Semaine couverte.
        update_mode: Si True, supprime les anciens events morez-events avant de recréer.
        dry_run: Simule sans créer.

    Returns:
        (créés, erreurs)
    """
    # Filtrer uniquement les events avec une date valide
    valid_events = [e for e in events if e.date and week_start <= e.date <= week_end]
    logger.info(f"Calendar: {len(valid_events)} événements avec date à synchroniser")

    if not valid_events:
        logger.warning("Aucun événement avec date valide à pousser vers Calendar")
        return 0, 0

    # En mode update, supprimer les anciens d'abord
    if update_mode and not dry_run:
        _delete_morez_events(week_start, week_end)

    created = 0
    errors = 0

    for ev in valid_events:
        try:
            # Construire les dates RFC3339
            start_dt = datetime.combine(ev.date, datetime.min.time().replace(hour=8))
            end_dt = start_dt + timedelta(hours=2)
            start_str = f"{ev.date.isoformat()}T08:00:00+01:00"
            end_str = f"{ev.date.isoformat()}T10:00:00+01:00"

            # Description avec tag + lien
            cat_label = config.CATEGORIES.get(ev.category, ev.category)
            description_parts = [
                f"{MOREZ_TAG} {cat_label}",
                f"📍 {ev.venue}" if ev.venue and ev.venue != ev.city else "",
                f"🌐 {ev.url}" if ev.url else "",
                f"Source: {ev.source}",
            ]
            description = "\n".join(p for p in description_parts if p)

            # Titre : emoji catégorie + titre + ville
            cat_emoji = {
                "concert": "🎵", "culture": "🎭",
                "sport": "⚽", "senior": "🧓", "autre": "🎪"
            }.get(ev.category, "📅")
            summary = f"{cat_emoji} {ev.title} — {ev.city}"[:100]

            cmd = [
                "gog", "calendar", "create", CALENDAR_ID,
                "--account", CALENDAR_ID,
                "--summary", summary,
                "--from", start_str,
                "--to", end_str,
                "--description", description,
                "--location", f"{ev.venue}, {ev.city}" if ev.venue and ev.venue != ev.city else ev.city,
            ]

            if dry_run:
                logger.info(f"[DRY RUN] Créerait: {summary} le {ev.date}")
                created += 1
                continue

            # Retry x3 sur erreur réseau
            import time
            for attempt in range(3):
                try:
                    subprocess.run(
                        cmd, env=_gog_env(), capture_output=True,
                        text=True, check=True, timeout=20
                    )
                    logger.debug(f"Créé: {summary}")
                    created += 1
                    break
                except subprocess.CalledProcessError as e:
                    if attempt == 2:
                        raise
                    logger.warning(f"Retry {attempt+1}/3 pour '{ev.title}': {e.stderr[:80]}")
                    time.sleep(2)
            time.sleep(0.4)  # Politesse API Google

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            msg = e.stderr.strip() if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f"Erreur création '{ev.title}': {msg[:100]}")
            errors += 1
        except Exception as e:
            logger.error(f"Erreur inattendue '{ev.title}': {e}")
            errors += 1

    logger.info(f"Calendar: {created} créés, {errors} erreurs")
    return created, errors
