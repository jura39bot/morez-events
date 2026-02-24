"""Génération du rapport hebdomadaire en Markdown."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from . import config
from .scraper import Event

logger = logging.getLogger(__name__)


def current_week_bounds() -> tuple[date, date]:
    """Retourne le lundi et le dimanche de la semaine en cours."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def format_date(ev: Event) -> str:
    """Formate la date d'un événement pour l'affichage."""
    if ev.date:
        jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        mois = [
            "jan", "fév", "mar", "avr", "mai", "jun",
            "jul", "aoû", "sep", "oct", "nov", "déc",
        ]
        d = ev.date
        jour = jours[d.weekday()]
        return f"{jour} {d.day} {mois[d.month - 1]}"
    return ev.date_str or "Date à confirmer"


def _make_table(events: List[Event]) -> str:
    """Génère un tableau Markdown pour une liste d'événements."""
    if not events:
        return "_Aucun événement trouvé pour cette catégorie._\n"

    lines = [
        "| Événement | Lieu | Ville | Date | Lien |",
        "|-----------|------|-------|------|------|",
    ]
    for ev in sorted(events, key=lambda e: (e.date or date.max, e.city)):
        title = ev.title.replace("|", "\\|")[:60]
        venue = ev.venue.replace("|", "\\|")[:30]
        city = ev.city
        d = format_date(ev)
        link = f"[🔗]({ev.url})" if ev.url else "—"
        lines.append(f"| {title} | {venue} | {city} | {d} | {link} |")

    return "\n".join(lines) + "\n"


def generate_report(
    events: List[Event],
    week_start: date,
    week_end: date,
    generated_at: Optional[date] = None,
    updated_at: Optional[date] = None,
) -> str:
    """Génère le rapport complet en Markdown."""
    if generated_at is None:
        generated_at = date.today()

    # En-tête
    fmt_start = week_start.strftime("%-d %B")
    fmt_end = week_end.strftime("%-d %B %Y")
    lines = [
        f"# 🗓️ Événements autour de Morez — Semaine du {fmt_start} au {fmt_end}",
        "",
        f"*Généré le {generated_at.strftime('%-d %B %Y')}*" +
        (f" | *Mis à jour le {updated_at.strftime('%-d %B %Y')}*" if updated_at and updated_at != generated_at else ""),
        "",
        f"> 📍 Rayon : ~1h de route depuis **Morez (Jura 39)**",
        f"> 🏙️ Villes couvertes : {', '.join(config.CITIES)}",
        "",
        "---",
        "",
    ]

    # Section par catégorie
    for cat_key, cat_label in config.CATEGORIES.items():
        cat_events = [e for e in events if e.category == cat_key]
        lines.append(f"## {cat_label}")
        lines.append("")
        lines.append(_make_table(cat_events))
        lines.append("")

    # Pied de page
    total = len(events)
    sources = sorted(set(ev.source for ev in events))
    lines += [
        "---",
        "",
        f"*{total} événement(s) recensé(s) · Sources : {', '.join(sources)}*",
        f"*Prochaine mise à jour : vendredi*",
        "",
    ]

    return "\n".join(lines)


def save_report(report_text: str, path: Optional[Path] = None) -> Path:
    """Sauvegarde le rapport dans un fichier."""
    path = path or config.REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    logger.info(f"Rapport sauvegardé : {path}")
    return path


def save_cache(events: List[Event], week_start: date, week_end: date) -> None:
    """Sauvegarde le cache des événements en JSON."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "generated_at": date.today().isoformat(),
        "events": [ev.to_dict() for ev in events],
    }
    config.EVENTS_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"Cache sauvegardé : {config.EVENTS_CACHE} ({len(events)} événements)")


def load_cache() -> Optional[dict]:
    """Charge le cache des événements si présent."""
    if not config.EVENTS_CACHE.exists():
        return None
    try:
        return json.loads(config.EVENTS_CACHE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Erreur lecture cache: {e}")
        return None


def cache_is_fresh(cache: dict, week_start: date) -> bool:
    """Vérifie si le cache correspond bien à la semaine en cours."""
    if not cache:
        return False
    return cache.get("week_start") == week_start.isoformat()
