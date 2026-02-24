"""Envoi du rapport hebdomadaire par email via le CLI gog."""

import logging
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger(__name__)


def build_subject(week_start: date, week_end: date) -> str:
    """Construit l'objet de l'email."""
    fmt_start = week_start.strftime("%-d %b")
    fmt_end = week_end.strftime("%-d %b %Y")
    return f"🗓️ Événements autour de Morez — Semaine du {fmt_start} au {fmt_end}"


def send_report(
    report_path: Path,
    week_start: date,
    week_end: date,
    subject: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    Envoie le rapport par email via le CLI gog.

    Args:
        report_path: Chemin vers le fichier rapport Markdown.
        week_start: Lundi de la semaine couverte.
        week_end: Dimanche de la semaine couverte.
        subject: Objet de l'email (auto-généré si None).
        dry_run: Si True, affiche la commande sans l'exécuter.

    Returns:
        True si l'envoi a réussi, False sinon.
    """
    if not report_path.exists():
        logger.error(f"Fichier rapport introuvable : {report_path}")
        return False

    if subject is None:
        subject = build_subject(week_start, week_end)

    cmd = [
        "gog", "gmail", "send",
        "--account", config.EMAIL_FROM,
        "--to", config.EMAIL_TO,
        "--subject", subject,
        "--body-file", str(report_path),
    ]

    env = os.environ.copy()
    env["GOG_KEYRING_PASSWORD"] = config.GOG_KEYRING_PASSWORD

    if dry_run:
        logger.info(f"[DRY RUN] Commande : {' '.join(cmd)}")
        logger.info(f"[DRY RUN] De : {config.EMAIL_FROM} → À : {config.EMAIL_TO}")
        print(f"[DRY RUN] Email qui serait envoyé :")
        print(f"  De      : {config.EMAIL_FROM}")
        print(f"  À       : {config.EMAIL_TO}")
        print(f"  Objet   : {subject}")
        print(f"  Rapport : {report_path}")
        return True

    logger.info(f"Envoi email : {config.EMAIL_FROM} → {config.EMAIL_TO}")
    logger.info(f"Objet : {subject}")

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Email envoyé avec succès")
        if result.stdout:
            logger.debug(f"stdout: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur envoi email (code {e.returncode}): {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("Commande 'gog' introuvable — vérifier l'installation")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi: {e}")
        return False
