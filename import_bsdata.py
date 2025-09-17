"""Command line utility to convert BSData catalogues into CSV extracts."""

import argparse
from contextlib import ExitStack
from pathlib import Path

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


if __name__ == "__main__":
    main()
