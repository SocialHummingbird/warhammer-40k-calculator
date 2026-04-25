"""Command line utility to convert BSData catalogues into CSV extracts."""

import argparse
from contextlib import ExitStack
from pathlib import Path
from datetime import UTC, datetime
import json as _json
import subprocess

from warhammer.github_fetch import GithubDownloadError, checkout_repository
from warhammer.importers.bsdata import import_catalogues
from warhammer.importers.schema import (
    ABILITY_HEADERS,
    KEYWORD_HEADERS,
    UNIT_HEADERS,
    UNIT_KEYWORD_HEADERS,
    WEAPON_HEADERS,
)
from warhammer.importers.writers import write_csv


def main() -> None:
    args = _parse_args()
    source_paths = [Path(path) for path in args.source]

    with ExitStack() as exit_stack:
        if args.github_repo:
            try:
                repo_path = exit_stack.enter_context(
                    checkout_repository(args.github_repo, ref=args.github_ref, subdir=args.github_subdir)
                )
            except GithubDownloadError as exc:
                raise SystemExit(str(exc)) from exc
            source_paths.append(repo_path)

        if not source_paths:
            raise SystemExit("No catalogue sources provided. Supply paths or use --github-repo.")

        units, weapons, abilities, keywords, unit_keywords = import_catalogues(source_paths)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(output_dir / "units.csv", units, UNIT_HEADERS)
    write_csv(output_dir / "weapons.csv", weapons, WEAPON_HEADERS)
    write_csv(output_dir / "abilities.csv", abilities, ABILITY_HEADERS)
    write_csv(output_dir / "keywords.csv", keywords, KEYWORD_HEADERS)
    write_csv(output_dir / "unit_keywords.csv", unit_keywords, UNIT_KEYWORD_HEADERS)

    # Write provenance metadata for reproducibility
    meta = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "counts": {
            "units": len(units),
            "weapons": len(weapons),
            "abilities": len(abilities),
            "keywords": len(keywords),
            "unit_keywords": len(unit_keywords),
        },
        "github_repo": args.github_repo,
        "github_ref": args.github_ref,
        "github_subdir": args.github_subdir,
        "sources": [str(p) for p in source_paths],
        "source_revisions": [_source_revision(p) for p in source_paths],
    }
    (output_dir / "metadata.json").write_text(_json.dumps(meta, indent=2), encoding="utf-8")

    print(
        "Exported "
        f"{len(units)} units, {len(weapons)} weapons, {len(abilities)} abilities, "
        f"{len(keywords)} keywords, {len(unit_keywords)} unit-keyword links to {output_dir}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import BattleScribe/BSData catalogues into CSV extracts")
    parser.add_argument(
        "source",
        nargs="*",
        help="One or more catalogue files or directories containing .cat/.gst files",
    )
    parser.add_argument(
        "--github-repo",
        help="Download catalogues from a GitHub repository, e.g. 'BSData/wh40k-10e'",
    )
    parser.add_argument(
        "--github-ref",
        default="main",
        help="Branch, tag, or ref to use with --github-repo (default: %(default)s)",
    )
    parser.add_argument(
        "--github-subdir",
        help="Optional subdirectory within the GitHub repository to limit catalogue discovery",
    )
    parser.add_argument(
        "--output",
        default="data",
        help="Directory where CSV extracts will be written (default: %(default)s)",
    )

    args = parser.parse_args()
    if args.github_subdir and not args.github_repo:
        parser.error("--github-subdir requires --github-repo")
    if not args.source and not args.github_repo:
        parser.error("Provide at least one source path or specify --github-repo")
    return args


def _source_revision(path: Path) -> dict[str, object]:
    """Return reproducibility metadata for a catalogue source path."""

    resolved = Path(path).resolve()
    details: dict[str, object] = {
        "path": str(path),
        "resolved_path": str(resolved),
    }
    git_root = _git_output(resolved, "rev-parse", "--show-toplevel")
    if not git_root:
        details["type"] = "filesystem"
        return details

    details["type"] = "git"
    details["git_root"] = git_root
    details["commit"] = _git_output(resolved, "rev-parse", "HEAD")
    details["branch"] = _git_output(resolved, "branch", "--show-current")
    details["remote_origin"] = _git_output(resolved, "remote", "get-url", "origin")
    details["dirty"] = bool(_git_output(resolved, "status", "--short"))
    return details


def _git_output(cwd: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


if __name__ == "__main__":
    main()
