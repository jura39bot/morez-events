"""CLI principal — morez-events."""

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from . import config
from .scraper import collect_events, Event
from .report import (
    current_week_bounds,
    generate_report,
    save_report,
    save_cache,
    load_cache,
    cache_is_fresh,
)
from .emailer import send_report
from .calendar_sync import push_events_to_calendar
from .drive_sync import push_report_to_drive

# ── Setup ────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="morez-events",
    help="📅 Rapport hebdomadaire d'événements autour de Morez (Jura) — ≤1h de route.",
    add_completion=False,
)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_or_collect(force: bool = False) -> tuple[list[Event], date, date]:
    """Charge le cache ou collecte les événements, selon la fraîcheur du cache."""
    week_start, week_end = current_week_bounds()

    if not force:
        cache = load_cache()
        if cache and cache_is_fresh(cache, week_start):
            from .scraper import Event as Ev
            events = [Ev.from_dict(d) for d in cache.get("events", [])]
            rprint(f"[dim]Cache chargé ({len(events)} événements, semaine du {week_start})[/dim]")
            return events, week_start, week_end

    # Pas de cache valide → collecte fraîche
    events = collect_events(week_start, week_end)
    save_cache(events, week_start, week_end)
    return events, week_start, week_end


# ── Commandes ────────────────────────────────────────────────────────────────

@app.command()
def generate(
    force: bool = typer.Option(False, "--force", "-f", help="Ignore le cache et re-scrape"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Chemin du rapport (défaut: data/weekly_report.md)"),
):
    """
    🔍 Génère le rapport de la semaine en cours.

    Collecte les événements depuis Brave Search et sortir.eu,
    génère le rapport Markdown et le sauvegarde.
    """
    rprint("[bold blue]📅 Génération du rapport hebdomadaire...[/bold blue]")

    events, week_start, week_end = _load_or_collect(force=force)

    if not events:
        rprint("[yellow]⚠️  Aucun événement trouvé cette semaine.[/yellow]")

    report_text = generate_report(events, week_start, week_end)
    report_path = save_report(report_text, output)

    # Résumé
    cats = {}
    for ev in events:
        cats[ev.category] = cats.get(ev.category, 0) + 1

    rprint(f"\n[green]✅ Rapport généré : {report_path}[/green]")
    rprint(f"   Semaine : {week_start.strftime('%-d %B')} → {week_end.strftime('%-d %B %Y')}")
    rprint(f"   Total   : {len(events)} événements")
    for cat, count in sorted(cats.items()):
        label = config.CATEGORIES.get(cat, cat)
        rprint(f"   {label} : {count}")


@app.command()
def update(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Chemin du rapport"),
):
    """
    🔄 Met à jour le rapport avec les dernières données.

    Force un re-scraping et régénère le rapport en indiquant la date de mise à jour.
    """
    rprint("[bold blue]🔄 Mise à jour du rapport...[/bold blue]")

    events, week_start, week_end = _load_or_collect(force=True)

    if not events:
        rprint("[yellow]⚠️  Aucun événement trouvé.[/yellow]")

    # Récupérer la date de génération initiale depuis le cache précédent
    generated_at = week_start  # Approximation si pas de cache
    old_cache = load_cache()
    if old_cache and old_cache.get("generated_at"):
        try:
            generated_at = date.fromisoformat(old_cache["generated_at"])
        except Exception:
            pass

    report_text = generate_report(
        events, week_start, week_end,
        generated_at=generated_at,
        updated_at=date.today(),
    )
    report_path = save_report(report_text, output)

    rprint(f"\n[green]✅ Rapport mis à jour : {report_path}[/green]")
    rprint(f"   {len(events)} événements recensés")


@app.command()
def email(
    dry_run: bool = typer.Option(False, "--dry-run", help="Simule l'envoi sans envoyer"),
    report_file: Optional[Path] = typer.Option(None, "--report", "-r", help="Rapport à envoyer"),
):
    """
    📧 Envoie le rapport par email à chetam70@gmail.com.

    Utilise le CLI gog (Gmail) pour l'envoi.
    Utilise le dernier rapport généré si --report n'est pas spécifié.
    """
    report_path = report_file or config.REPORT_PATH

    if not report_path.exists():
        rprint(f"[red]❌ Rapport introuvable : {report_path}[/red]")
        rprint("[dim]Lancez d'abord : morez-events generate[/dim]")
        raise typer.Exit(1)

    week_start, week_end = current_week_bounds()

    rprint(f"[bold blue]📧 Envoi du rapport par email...[/bold blue]")
    rprint(f"   De  : {config.EMAIL_FROM}")
    rprint(f"   À   : {config.EMAIL_TO}")

    success = send_report(report_path, week_start, week_end, dry_run=dry_run)

    if success:
        rprint(f"\n[green]✅ Email envoyé avec succès ![/green]")
    else:
        rprint(f"\n[red]❌ Échec de l'envoi de l'email.[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    monday: bool = typer.Option(False, "--monday", help="Mode lundi : générer le rapport"),
    friday: bool = typer.Option(False, "--friday", help="Mode vendredi : mettre à jour + envoyer"),
):
    """
    🗓️ Exécution complète selon le jour (lundi ou vendredi).

    --monday : Collecte + génère le rapport de la semaine.
    --friday : Re-collecte + met à jour + envoie par email.
    """
    if not monday and not friday:
        rprint("[red]Précisez --monday ou --friday[/red]")
        raise typer.Exit(1)

    if monday and friday:
        rprint("[red]Précisez un seul mode : --monday OU --friday[/red]")
        raise typer.Exit(1)

    week_start, week_end = current_week_bounds()

    if monday:
        rprint("[bold]📅 Mode LUNDI — génération rapport + sync Calendar[/bold]")
        rprint(f"Semaine du {week_start.strftime('%-d %B')} au {week_end.strftime('%-d %B %Y')}")

        events = collect_events(week_start, week_end)
        save_cache(events, week_start, week_end)
        report_text = generate_report(events, week_start, week_end)
        report_path = save_report(report_text)

        rprint(f"\n[green]✅ Rapport généré : {report_path}[/green]")
        rprint(f"   {len(events)} événements recensés")

        # Sync Google Calendar (création initiale)
        rprint("\n[blue]📅 Sync Google Calendar...[/blue]")
        created, errors = push_events_to_calendar(
            events, week_start, week_end, update_mode=False
        )
        rprint(f"   [green]{created} événements ajoutés au Calendar[/green]"
               + (f" | [red]{errors} erreurs[/red]" if errors else ""))

    elif friday:
        rprint("[bold]🔄 Mode VENDREDI — mise à jour + email + Calendar[/bold]")

        # Re-collecte pour mise à jour
        events = collect_events(week_start, week_end)
        save_cache(events, week_start, week_end)

        old_cache = load_cache()
        generated_at = date.today()
        if old_cache and old_cache.get("generated_at"):
            try:
                generated_at = date.fromisoformat(old_cache["generated_at"])
            except Exception:
                pass

        report_text = generate_report(
            events, week_start, week_end,
            generated_at=generated_at,
            updated_at=date.today(),
        )
        report_path = save_report(report_text)

        rprint(f"   {len(events)} événements recensés")

        # Mise à jour Google Calendar (supprime + recrée)
        rprint("\n[blue]📅 Mise à jour Google Calendar...[/blue]")
        created, errors = push_events_to_calendar(
            events, week_start, week_end, update_mode=True
        )
        rprint(f"   [green]{created} événements mis à jour dans le Calendar[/green]"
               + (f" | [red]{errors} erreurs[/red]" if errors else ""))

        # Push vers Google Drive
        rprint("\n[blue]📄 Push vers Google Drive...[/blue]")
        drive_success = push_report_to_drive(report_path, week_start, week_end)
        if drive_success:
            rprint("   [green]✅ Rapport poussé dans Google Docs[/green]")
        else:
            rprint("   [yellow]⚠️ Échec push Drive[/yellow]")
        
        # Envoi email
        success = send_report(report_path, week_start, week_end)
        if success:
            rprint(f"\n[green]✅ Email envoyé à {config.EMAIL_TO}[/green]")
        else:
            rprint(f"\n[red]❌ Échec envoi email[/red]")
            raise typer.Exit(1)


@app.command(name="sync-calendar")
def sync_calendar(
    update: bool = typer.Option(False, "--update", "-u", help="Supprime et recrée (mise à jour)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simule sans créer"),
):
    """
    📅 Synchronise les événements vers Google Calendar (jura39bot@gmail.com).

    Par défaut, ajoute les nouveaux événements sans toucher aux existants.
    Avec --update, supprime les anciens événements morez-events et recrée tout.
    """
    cache = load_cache()
    if not cache:
        rprint("[yellow]Aucun cache — lancez d'abord : morez-events generate[/yellow]")
        raise typer.Exit(1)

    from .scraper import Event as Ev
    events = [Ev.from_dict(d) for d in cache.get("events", [])]
    week_start = date.fromisoformat(cache["week_start"])
    week_end = date.fromisoformat(cache["week_end"])

    mode = "mise à jour" if update else "ajout"
    rprint(f"[bold blue]📅 Sync Calendar ({mode}) — {len(events)} événements[/bold blue]")
    rprint(f"   Semaine : {week_start} → {week_end}")
    rprint(f"   Compte  : jura39bot@gmail.com")

    created, errors = push_events_to_calendar(
        events, week_start, week_end,
        update_mode=update,
        dry_run=dry_run,
    )

    if dry_run:
        rprint(f"\n[dim][DRY RUN] {created} événements auraient été créés[/dim]")
    else:
        rprint(f"\n[green]✅ {created} événements dans Google Calendar[/green]"
               + (f"\n[red]⚠️  {errors} erreurs[/red]" if errors else ""))


@app.command()
def show(
    cat: Optional[str] = typer.Argument(None, help="Filtrer par catégorie (concert/culture/sport/autre)"),
):
    """
    👀 Affiche le dernier rapport en mode tableau dans le terminal.
    """
    cache = load_cache()
    if not cache:
        rprint("[yellow]Aucun rapport disponible — lancez : morez-events generate[/yellow]")
        raise typer.Exit(1)

    from .scraper import Event as Ev
    events = [Ev.from_dict(d) for d in cache.get("events", [])]

    if cat:
        events = [e for e in events if e.category == cat.lower()]

    if not events:
        rprint(f"[yellow]Aucun événement{f' pour la catégorie {cat}' if cat else ''}[/yellow]")
        raise typer.Exit(0)

    week_start = date.fromisoformat(cache["week_start"])
    week_end = date.fromisoformat(cache["week_end"])

    console.print(f"\n[bold]📅 Événements — semaine du {week_start.strftime('%-d %B')} au {week_end.strftime('%-d %B %Y')}[/bold]\n")

    for cat_key, cat_label in config.CATEGORIES.items():
        cat_events = [e for e in events if e.category == cat_key]
        if not cat_events:
            continue

        table = Table(title=cat_label, show_lines=True)
        table.add_column("Événement", style="bold", max_width=40)
        table.add_column("Lieu", max_width=25)
        table.add_column("Ville")
        table.add_column("Date")

        for ev in sorted(cat_events, key=lambda e: (e.date or date.max)):
            from .report import format_date
            table.add_row(
                ev.title[:40],
                ev.venue[:25],
                ev.city,
                format_date(ev),
            )
        console.print(table)
        console.print()


# ── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
