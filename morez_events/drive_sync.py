"""Synchronisation du rapport vers Google Drive (Docs)."""

import json
import logging
import os
import subprocess
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ID du Google Doc Veille_Tech
VEILLE_TECH_DOC_ID = "1L850TuoIYrtU0taC4Eq28wHDB8wYBIpldDQ2MaTImrc"


def _refresh_access_token() -> str:
    """Rafraîchit le token OAuth via le script."""
    try:
        result = subprocess.run(
            ["bash", "/root/clawd/scripts/gmail-token-refresh.sh"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.error(f"Erreur refresh token: {result.stderr}")
            raise Exception("Échec du rafraîchissement du token")
        
        # Lire le token frais
        token_file = os.path.expanduser("~/.config/gogcli/tokens/jurabot39@gmail.com.json")
        with open(token_file) as f:
            data = json.load(f)
        return data["access_token"]
    except Exception as e:
        logger.error(f"Impossible de rafraîchir le token: {e}")
        raise


def _get_access_token() -> str:
    """Récupère le token (avec refresh si nécessaire)."""
    try:
        # Essayer de lire le token actuel
        token_file = os.path.expanduser("~/.config/gogcli/tokens/jurabot39@gmail.com.json")
        with open(token_file) as f:
            data = json.load(f)
        return data["access_token"]
    except:
        # Si échec, rafraîchir
        return _refresh_access_token()


def push_report_to_drive(report_path: Path, week_start: date, week_end: date) -> bool:
    """
    Pousse le rapport dans le Google Doc Veille_Tech.
    
    Args:
        report_path: Chemin du fichier Markdown
        week_start: Début de la semaine
        week_end: Fin de la semaine
        
    Returns:
        True si succès, False sinon
    """
    try:
        # Rafraîchir le token avant l'appel
        access_token = _refresh_access_token()
        
        # Lire le contenu du rapport
        with open(report_path, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # Préparer le contenu à insérer
        header = f"""# 📅 Événements Morez — Semaine du {week_start.strftime('%-d %B')} au {week_end.strftime('%-d %B %Y')}

"""
        
        content = header + report_content
        
        # Requête pour insérer au début du document
        requests = {
            "requests": [
                {
                    "insertText": {
                        "location": {
                            "index": 1
                        },
                        "text": content
                    }
                }
            ]
        }
        
        url = f"https://docs.googleapis.com/v1/documents/{VEILLE_TECH_DOC_ID}:batchUpdate"
        req = urllib.request.Request(
            url,
            data=json.dumps(requests).encode(),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            logger.info(f"Google Doc mis à jour: {len(result.get('replies', []))} révisions")
            return True
            
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP Error {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as e:
        logger.error(f"Erreur push Drive: {e}")
        return False
