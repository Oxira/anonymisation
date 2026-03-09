"""
Command-line interface for the PDF anonymisation tool.

Usage examples:
    # Single file
    python cli.py input.pdf output.pdf

    # Single file, auto-generated output name
    python cli.py input.pdf

    # Batch mode: process all PDFs in a directory
    python cli.py --batch ./pdfs_entree/ --output ./pdfs_anonymises/

    # With options
    python cli.py input.pdf --dpi 400 --verbose --engine tesseract
"""
from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("input_pdf", required=False)
@click.argument("output_pdf", required=False)
@click.option("--batch", "-b", "batch_dir", default=None, metavar="DIRECTORY",
              help="Traiter tous les PDFs d'un dossier.")
@click.option("--output", "-o", "output_dir", default=None, metavar="DIRECTORY",
              help="Dossier de sortie pour le mode batch.")
@click.option("--suffix", "-s", default="_anonymise", show_default=True,
              help="Suffixe ajouté au nom de fichier en mode batch.")
@click.option("--dpi", "-d", default=300, show_default=True,
              help="Résolution OCR en DPI (300 recommandé).")
@click.option("--engine", "-e", default="auto",
              type=click.Choice(["auto", "tesseract", "easyocr"], case_sensitive=False),
              show_default=True, help="Moteur OCR à utiliser.")
@click.option("--verbose", "-v", is_flag=True, help="Afficher le détail des PII détectées.")
def main(
    input_pdf: str,
    output_pdf: str,
    batch_dir: str,
    output_dir: str,
    suffix: str,
    dpi: int,
    engine: str,
    verbose: bool,
) -> None:
    """
    Anonymise les données personnelles dans des PDFs image.

    Redacte : nom de famille, email, adresse, téléphone, N° sécu, CNI, CB.
    Conserve : le prénom.
    """
    if not batch_dir and not input_pdf:
        click.echo("Erreur : spécifiez un fichier PDF ou utilisez --batch.", err=True)
        sys.exit(1)

    click.echo("Chargement du modèle NLP (spaCy fr_core_news_lg)…")
    from anonymiser.detector import load_nlp_model
    nlp = load_nlp_model()
    click.echo("Modèle chargé.")

    if batch_dir:
        _run_batch(batch_dir, output_dir, nlp, dpi, engine, suffix, verbose)
    else:
        _run_single(input_pdf, output_pdf, nlp, dpi, engine, suffix, verbose)


def _run_single(
    input_pdf: str,
    output_pdf: str,
    nlp,
    dpi: int,
    engine: str,
    suffix: str,
    verbose: bool,
) -> None:
    src = Path(input_pdf)
    if not src.exists():
        click.echo(f"Erreur : fichier introuvable : {input_pdf}", err=True)
        sys.exit(1)

    if output_pdf:
        dst = Path(output_pdf)
    else:
        dst = src.parent / (src.stem + suffix + ".pdf")

    click.echo(f"Traitement : {src.name}")

    from anonymiser.pipeline import process_pdf

    def progress_cb(current: int, total: int) -> None:
        if total > 0:
            pct = int(current / total * 100)
            click.echo(f"\r  Page {current}/{total} ({pct}%)", nl=False)

    n = process_pdf(str(src), str(dst), nlp, dpi=dpi, ocr_engine=engine,
                    progress_cb=progress_cb)
    click.echo(f"\r  ✓ {dst.name} — {n} zone(s) redactée(s)          ")


def _run_batch(
    batch_dir: str,
    output_dir: str,
    nlp,
    dpi: int,
    engine: str,
    suffix: str,
    verbose: bool,
) -> None:
    from anonymiser.pipeline import process_directory

    out = output_dir or batch_dir
    Path(out).mkdir(parents=True, exist_ok=True)

    click.echo(f"Traitement du dossier : {batch_dir}")
    click.echo(f"Sortie vers           : {out}")

    results = process_directory(
        batch_dir, out, nlp, dpi=dpi, ocr_engine=engine, suffix=suffix
    )

    total = sum(results.values())
    click.echo(f"\nRésumé : {len(results)} fichier(s) traité(s), {total} zone(s) redactée(s) au total.")
    if verbose:
        for filename, n in results.items():
            click.echo(f"  {filename} : {n} redaction(s)")


if __name__ == "__main__":
    main()
