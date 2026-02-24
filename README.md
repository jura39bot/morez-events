# 🗓️ morez-events

Outil CLI Python pour générer un **rapport hebdomadaire des événements culturels et sportifs** dans un rayon d'1h de **Morez (Jura, France)**.

Concerts, théâtre, spectacles, matchs, festivals — tout ce qui se passe à moins d'une heure de route.

---

## Fonctionnement

| Quand | Action |
|-------|--------|
| **Lundi 7h** | Génération du rapport de la semaine (cron auto) |
| **Vendredi 17h** | Mise à jour + envoi par email à `chetam70@gmail.com` |

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/ton-compte/morez-events.git
cd morez-events
```

### 2. Installer les dépendances

```bash
pip install -e .
# ou
pip install -r requirements.txt
```

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
# Éditer .env et mettre ta clé Brave API
nano .env
```

**Obtenir une clé Brave Search API (gratuit) :**
1. Aller sur https://api.search.brave.com/
2. Créer un compte
3. Récupérer la clé dans le dashboard
4. La mettre dans `.env` : `BRAVE_API_KEY=sk-...`

---

## Usage CLI

```bash
# Générer le rapport de la semaine
morez-events generate

# Forcer un re-scraping (ignore le cache)
morez-events generate --force

# Mettre à jour le rapport (vendredi)
morez-events update

# Envoyer le rapport par email
morez-events email

# Mode lundi (génération)
morez-events run --monday

# Mode vendredi (mise à jour + email)
morez-events run --friday

# Afficher le rapport dans le terminal
morez-events show

# Filtrer par catégorie
morez-events show concert
morez-events show sport
morez-events show culture
```

---

## Cron — Configuration automatique

Éditer la crontab :

```bash
crontab -e
```

Ajouter ces deux lignes :

```cron
# Lundi 7h00 — génération rapport
0 7 * * 1 /root/Projects/morez-events/scripts/monday_run.sh >> /root/Projects/morez-events/data/cron.log 2>&1

# Vendredi 17h00 — mise à jour + email
0 17 * * 5 /root/Projects/morez-events/scripts/friday_run.sh >> /root/Projects/morez-events/data/cron.log 2>&1
```

Logs disponibles dans `data/cron.log`.

---

## Villes couvertes (≤1h de Morez)

| Ville | Département |
|-------|-------------|
| Morez | Jura (39) |
| Saint-Claude | Jura (39) |
| Lons-le-Saunier | Jura (39) |
| Champagnole | Jura (39) |
| Pontarlier | Doubs (25) |
| Oyonnax | Ain (01) |
| Bourg-en-Bresse | Ain (01) |
| Dole | Jura (39) |
| Poligny | Jura (39) |
| Clairvaux-les-Lacs | Jura (39) |

---

## Sources de données

| Source | Type |
|--------|------|
| [Brave Search API](https://api.search.brave.com/) | Recherche web (concerts, spectacles, sport) |
| [sortir.eu](https://www.sortir.eu/) | Scraping agenda local |

---

## Structure du projet

```
morez-events/
├── morez_events/
│   ├── __init__.py
│   ├── cli.py          # CLI principal (Typer)
│   ├── scraper.py      # Collecte événements (Brave + sortir.eu)
│   ├── report.py       # Génération rapport Markdown
│   ├── emailer.py      # Envoi email via gog CLI
│   └── config.py       # Configuration
├── data/               # Rapports et cache (gitignorés)
├── scripts/
│   ├── monday_run.sh   # Script cron lundi
│   └── friday_run.sh   # Script cron vendredi
├── .env.example
├── requirements.txt
├── setup.py
└── README.md
```

---

## Rapport généré

Le rapport Markdown est sauvegardé dans `data/weekly_report.md` :

```markdown
# 🗓️ Événements autour de Morez — Semaine du 24 fév au 1 mars 2026

> 📍 Rayon : ~1h de route depuis Morez (Jura 39)

## 🎵 Concerts & Musique
| Événement | Lieu | Ville | Date | Lien |
|-----------|------|-------|------|------|
| ...       | ...  | ...   | ...  | ...  |

## 🎭 Culture & Spectacles
...

## ⚽ Sports
...
```

---

*Projet personnel — Mathieu Chevalier, Morez (Jura)*
