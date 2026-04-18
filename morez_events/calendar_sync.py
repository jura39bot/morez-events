"""Synchronisation des événements vers Google Calendar via API REST (urllib)."""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from typing import List, Optional, Set

from . import config
from .scraper import Event

logger = logging.getLogger(__name__)

CALENDAR_ID = "jura39bot@gmail.com"
SENIOR_CALENDAR_ID = "29b81e92f0654272030cf9c64a347b20f219e58c7347b1e36a2ab0445b19a0ae@group.calendar.google.com"
MOREZ_TAG = "[morez-events]"


def _get_access_token() -> str:
    """Récupère un access token frais depuis le fichier."""
    try:
        token_file = os.path.expanduser("~/.config/gogcli/tokens/jurabot39@gmail.com.json")
        with open(token_file) as f:
            data = json.load(f)
        return data["access_token"]
    except Exception as e:
        logger.error(f"Impossible de lire le token: {e}")
        raise


def _api_call(method: str, endpoint: str, data: dict = None, params: dict = None) -> Optional[dict]:
    """Appelle l'API Google Calendar avec urllib."""
    token = _get_access_token()
    base_url = "https://www.googleapis.com/calendar/v3"
    
    # Construire l'URL avec params
    url = f"{base_url}{endpoint}"
    if params:
        query = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{query}"
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json" if data else ""
        },
        method=method
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_data = response.read()
            return json.loads(resp_data) if resp_data else {}
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        logger.error(f"API call erreur: {e}")
        return None


def _list_events(calendar_id: str, time_min: str, time_max: str) -> List[dict]:
    """Liste les événements d'un calendrier."""
    events = []
    page_token = None
    
    while True:
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "maxResults": "250"
        }
        if page_token:
            params["pageToken"] = page_token
        
        result = _api_call("GET", f"/calendars/{calendar_id}/events", params=params)
        if not result:
            break
        
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    
    return events


def _existing_morez_events(week_start: date, week_end: date, calendar_id: str = CALENDAR_ID) -> Set[str]:
    """Récupère les IDs des événements morez-events déjà dans le calendar."""
    try:
        time_min = f"{week_start.isoformat()}T00:00:00+02:00"
        time_max = f"{week_end.isoformat()}T23:59:59+02:00"
        
        events = _list_events(calendar_id, time_min, time_max)
        ids = {ev.get("id", "") for ev in events 
               if MOREZ_TAG in (ev.get("description", "") + ev.get("summary", ""))}
        
        logger.info(f"Calendar {calendar_id[:30]}…: {len(ids)} événements existants")
        return ids
    except Exception as e:
        logger.warning(f"Impossible de récupérer les events: {e}")
        return set()


def _delete_event(event_id: str, calendar_id: str) -> bool:
    """Supprime un événement."""
    result = _api_call("DELETE", f"/calendars/{calendar_id}/events/{event_id}")
    return result is not None


def _delete_morez_events(week_start: date, week_end: date, calendar_id: str) -> int:
    """Supprime les événements morez-events existants."""
    deleted = 0
    try:
        for event_id in _existing_morez_events(week_start, week_end, calendar_id):
            if event_id and _delete_event(event_id, calendar_id):
                deleted += 1
    except Exception as e:
        logger.warning(f"Erreur suppression: {e}")
    
    logger.info(f"Calendar {calendar_id[:30]}…: {deleted} supprimés")
    return deleted


def _create_event(ev: Event, calendar_id: str) -> bool:
    """Crée un événement dans Google Calendar."""
    try:
        # Dates (heure d'été = +02:00)
        start_str = f"{ev.date.isoformat()}T08:00:00+02:00"
        end_str = f"{ev.date.isoformat()}T10:00:00+02:00"
        
        cat_label = config.CATEGORIES.get(ev.category, ev.category)
        desc_parts = [
            f"{MOREZ_TAG} {cat_label}",
            f"📍 {ev.venue}" if ev.venue and ev.venue != ev.city else "",
            f"🌐 {ev.url}" if ev.url else "",
        ]
        description = "\n".join(p for p in desc_parts if p)
        
        emoji = {"concert": "🎵", "culture": "🎭", "sport": "⚽", "senior": "🧓"}.get(ev.category, "📅")
        summary = f"{emoji} {ev.title} — {ev.city}"[:100]
        location = f"{ev.venue}, {ev.city}" if ev.venue and ev.venue != ev.city else ev.city
        
        event_data = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start_str, "timeZone": "Europe/Paris"},
            "end": {"dateTime": end_str, "timeZone": "Europe/Paris"}
        }
        
        result = _api_call("POST", f"/calendars/{calendar_id}/events", data=event_data)
        return result is not None and "id" in result
        
    except Exception as e:
        logger.error(f"Erreur création: {e}")
        return False


def push_events_to_calendar(
    events: List[Event],
    week_start: date,
    week_end: date,
    update_mode: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Pousse les événements vers Google Calendar."""
    valid_events = [e for e in events if e.date and week_start <= e.date <= week_end]
    logger.info(f"Calendar: {len(valid_events)} événements à synchroniser")

    if not valid_events:
        return 0, 0

    # Supprimer anciens events si mode update
    if update_mode and not dry_run:
        _delete_morez_events(week_start, week_end, CALENDAR_ID)
        _delete_morez_events(week_start, week_end, SENIOR_CALENDAR_ID)

    created = 0
    errors = 0

    for ev in valid_events:
        target_cal = SENIOR_CALENDAR_ID if ev.category == "senior" else CALENDAR_ID
        
        if dry_run:
            logger.info(f"[DRY] {ev.title} → {target_cal[:20]}")
            created += 1
            continue

        # Retry x2
        for attempt in range(2):
            if _create_event(ev, target_cal):
                created += 1
                break
            if attempt == 1:
                errors += 1
                logger.error(f"Échec: {ev.title}")
            time.sleep(1)
        
        time.sleep(0.1)  # Rate limiting

    logger.info(f"Calendar: {created} créés, {errors} erreurs")
    return created, errors
