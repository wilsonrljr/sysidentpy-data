"""Build SysIdentPy companion book PDF and EPUB artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

BOOK_AUTHOR = "Wilson R. L. Junior"
COVER_IMAGE = "book/assets/Nonlinear_System_identification.png"
CHAPTERS = (
    "0-Preface.md",
    "0.1-Contents.md",
    "1-Introduction.md",
    "2-NARMAX-Model-Representation.md",
    "3-Parameter-Estimation.md",
    "4-Model-Structure-Selection.md",
    "5-Multiobjective-Parameter-Estimation.md",
    "6-Multiobjective-Model-Structure-Selection.md",
    "7-NARX-Neural-Network.md",
    "8-Severely-Nonlinear-System-Identification.md",
    "9-Validation.md",
    "10-Case-Studies.md",
)
BOOKS = {
    "en": {
        "book_dir": Path("docs/en/book"),
        "title": (
            "Nonlinear System Identification and Forecasting: "
            "Theory and Practice With SysIdentPy"
        ),
        "lang": "en-US",
        "file_stem": (
            "Nonlinear_System_Identification_Theory_and_Practice_With_"
            "SysIdentPy_Wilson_R_L_Junior"
        ),
    },
    "pt-BR": {
        "book_dir": Path("docs/pt/book"),
        "title": (
            "Identificação de Sistemas Não Lineares e Previsão: "
            "Teoria e Prática Com SysIdentPy"
        ),
        "lang": "pt-BR",
        "file_stem": (
            "Identificacao_de_Sistemas_Nao_Lineares_e_Previsao_"
            "Teoria_e_Pratica_Com_SysIdentPy_Wilson_R_L_Junior"
        ),
    },
}

DOWNLOAD_SECTION_RE = re.compile(
    r"\n## (?:PDF and EPUB versions|PDF, Epub and Mobi version|"
    r"Versões em PDF e EPUB|Versões em PDF, Epub e Mobi)\n.*?(?=\n## )",
    re.DOTALL,
)
MKDOCS_ATTR_RE = re.compile(r"\)\{:[^}\n]+\}")
LATEX_TAG_RE = re.compile(r"\\tag\{([^}]+)\}")
GITHUB_ASSET_RE = re.compile(
    r"https://github\.com/wilsonrljr/sysidentpy-data/blob/[^/]+/"
    r"book/assets/([^)\n?]+)(?:\?raw=true)?"
)
RAW_ASSET_RE = re.compile(
    r"https://raw\.githubusercontent\.com/wilsonrljr/sysidentpy-data/[^/]+/"
    r"book/assets/([^)\n?]+)"
)


def main() -> None:
    """Build book artifacts from the SysIdentPy Markdown source."""
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    data_root = Path(__file__).resolve().parents[1]
    languages = tuple(BOOKS) if args.language == "all" else (args.language,)

    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required to build book artifacts")

    assets_dir = data_root / "book" / "assets"
    output.mkdir(parents=True, exist_ok=True)

    books = []
    for language in languages:
        config = BOOKS[language]
        book_dir = source / config["book_dir"]
        validate_inputs(source, book_dir, assets_dir)

        combined_markdown = output / f"book-{language}.md"
        combined_markdown.write_text(
            build_combined_markdown(book_dir, config),
            encoding="utf-8",
        )

        file_stem = str(config["file_stem"])
        pdf_path = output / f"{file_stem}.pdf"
        epub_path = output / f"{file_stem}.epub"
        run_pandoc_pdf(combined_markdown, pdf_path, data_root, book_dir, config)
        run_pandoc_epub(combined_markdown, epub_path, data_root, book_dir, config)
        books.append(
            {
                "language": language,
                "title": config["title"],
                "artifacts": (pdf_path, epub_path),
            }
        )

    write_manifest(output, source, books)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build SysIdentPy companion book PDF and EPUB artifacts.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the SysIdentPy repository checkout.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory where generated artifacts will be written.",
    )
    parser.add_argument(
        "--language",
        choices=(*BOOKS, "all"),
        default="en",
        help="Book language to build.",
    )
    return parser.parse_args()


def validate_inputs(source: Path, book_dir: Path, assets_dir: Path) -> None:
    """Validate source and asset paths before invoking Pandoc."""
    if not (source / "sysidentpy").is_dir():
        raise SystemExit(f"{source}: not a SysIdentPy repository checkout")
    if not book_dir.is_dir():
        raise SystemExit(f"{book_dir}: book source directory not found")
    if not assets_dir.is_dir():
        raise SystemExit(f"{assets_dir}: book assets directory not found")

    missing = [chapter for chapter in CHAPTERS if not (book_dir / chapter).is_file()]
    if missing:
        raise SystemExit("missing book chapters: " + ", ".join(missing))


def build_combined_markdown(book_dir: Path, config: dict[str, object]) -> str:
    """Return one sanitized Markdown document for Pandoc."""
    parts = [metadata_block(config)]
    for chapter in CHAPTERS:
        markdown = (book_dir / chapter).read_text(encoding="utf-8")
        if chapter == "0-Preface.md":
            markdown = remove_download_section(markdown)
        parts.append(sanitize_markdown(markdown))
    return "\n\n".join(parts).strip() + "\n"


def metadata_block(config: dict[str, object]) -> str:
    """Return Pandoc metadata for the generated book."""
    today = datetime.now(timezone.utc).date().isoformat()
    return "\n".join(
        (
            "---",
            f'title: "{config["title"]}"',
            f'author: "{BOOK_AUTHOR}"',
            f"lang: {config['lang']}",
            f"date: {today}",
            "---",
        )
    )


def remove_download_section(markdown: str) -> str:
    """Remove website-only download links from the generated artifact."""
    return DOWNLOAD_SECTION_RE.sub("\n", markdown)


def sanitize_markdown(markdown: str) -> str:
    """Adapt MkDocs-oriented Markdown to Pandoc input."""
    markdown = markdown.replace("\t", "    ")
    markdown = markdown.replace("\u200b", "")
    markdown = markdown.replace("\u00a0", " ")
    markdown = LATEX_TAG_RE.sub(r"\\qquad\\text{(\1)}", markdown)
    markdown = MKDOCS_ATTR_RE.sub(")", markdown)
    markdown = GITHUB_ASSET_RE.sub(rewrite_asset_url, markdown)
    markdown = RAW_ASSET_RE.sub(rewrite_asset_url, markdown)
    return markdown


def rewrite_asset_url(match: re.Match[str]) -> str:
    """Rewrite a sysidentpy-data asset URL to a local Pandoc resource path."""
    asset_name = unquote(match.group(1))
    asset_path = Path(asset_name)
    if asset_path.name != asset_name:
        raise SystemExit(f"unexpected nested book asset path: {asset_name}")
    return quote(f"book/assets/{asset_name}", safe="/.")


def run_pandoc_pdf(
    markdown: Path,
    output: Path,
    data_root: Path,
    book_dir: Path,
    config: dict[str, object],
) -> None:
    """Build the PDF artifact with Pandoc and XeLaTeX."""
    run_pandoc(
        markdown,
        output,
        data_root,
        book_dir,
        config,
        extra_args=[
            "--pdf-engine=xelatex",
            "--toc",
            "--number-sections",
            "--variable=documentclass:book",
            "--variable=geometry:margin=1in",
            "--variable=colorlinks:true",
            "--variable=linkcolor:blue",
            "--variable=urlcolor:blue",
        ],
    )


def run_pandoc_epub(
    markdown: Path,
    output: Path,
    data_root: Path,
    book_dir: Path,
    config: dict[str, object],
) -> None:
    """Build the EPUB artifact with Pandoc."""
    run_pandoc(
        markdown,
        output,
        data_root,
        book_dir,
        config,
        extra_args=[
            "--toc",
            "--standalone",
            f"--epub-cover-image={COVER_IMAGE}",
        ],
    )


def run_pandoc(
    markdown: Path,
    output: Path,
    data_root: Path,
    book_dir: Path,
    config: dict[str, object],
    *,
    extra_args: list[str],
) -> None:
    """Run Pandoc with common options."""
    title = str(config["title"])
    command = [
        "pandoc",
        str(markdown),
        "--from=markdown+tex_math_dollars+pipe_tables+raw_html",
        f"--resource-path={data_root}{os.pathsep}{book_dir}",
        f"--metadata=title:{title}",
        f"--metadata=author:{BOOK_AUTHOR}",
        f"--output={output}",
        *extra_args,
    ]
    subprocess.run(command, cwd=data_root, check=True)


def write_manifest(
    output: Path,
    source: Path,
    books: list[dict[str, object]],
) -> None:
    """Write a small reproducibility manifest for the generated artifacts."""
    manifest = {
        "source_repository": "wilsonrljr/sysidentpy",
        "source_commit": source_commit(source),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "books": [
            {
                "language": book["language"],
                "title": book["title"],
                "artifacts": [
                    {
                        "file": artifact.name,
                        "sha256": sha256(artifact),
                        "size_bytes": artifact.stat().st_size,
                    }
                    for artifact in book["artifacts"]
                ],
            }
            for book in books
        ],
    }
    (output / "book-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def source_commit(source: Path) -> str:
    """Return the source checkout commit hash, or unknown outside Git."""
    completed = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout.strip()
    return "unknown"


def sha256(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
