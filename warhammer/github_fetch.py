"""Helpers for downloading catalogues directly from GitHub."""

from __future__ import annotations

import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_USER_AGENT = "warhammer-calculator/1.0"


class GithubDownloadError(RuntimeError):
    """Raised when GitHub catalogue download fails."""


def _ref_candidates(ref: str) -> Iterator[str]:
    seen = set()
    for candidate in (ref, "main", "master"):
        if not candidate:
            continue
        key = candidate if candidate.startswith("refs/") else candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        yield candidate


def _build_archive_urls(repo: str, ref: str) -> Iterator[tuple[str, str]]:
    """Yield (ref, url) pairs for possible archive locations."""
    for candidate in _ref_candidates(ref):
        if candidate.startswith("refs/"):
            yield candidate, f"https://codeload.github.com/{repo}/zip/{candidate}"
            continue
        yield candidate, f"https://codeload.github.com/{repo}/zip/refs/heads/{candidate}"
        yield candidate, f"https://codeload.github.com/{repo}/zip/refs/tags/{candidate}"


def _download_archive(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _extract_archive(archive_path: Path, extract_dir: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)
        root_name = None
        for name in archive.namelist():
            if not name:
                continue
            parts = name.split("/", 1)
            if parts:
                root_name = parts[0]
                break
        if not root_name:
            raise GithubDownloadError("Archive did not contain any files")
    archive_path.unlink(missing_ok=True)
    root_path = extract_dir / root_name
    if not root_path.exists():
        raise GithubDownloadError("Extracted archive is missing expected root directory")
    return root_path


def _resolve_subdir(root: Path, subdir: str | None) -> Path:
    if not subdir:
        return root
    sub_path = Path(*Path(subdir).parts)
    resolved = root / sub_path
    if not resolved.exists():
        raise GithubDownloadError(f"Subdirectory '{subdir}' not found in repository")
    return resolved


@contextmanager
def checkout_repository(repo: str, *, ref: str = "main", subdir: str | None = None) -> Iterator[Path]:
    """Checkout a GitHub repository archive into a temporary directory."""

    temp_dir = Path(tempfile.mkdtemp(prefix="wh40k-github-"))
    try:
        archive_path = temp_dir / "archive.zip"
        errors: list[str] = []
        for resolved_ref, url in _build_archive_urls(repo, ref):
            try:
                _download_archive(url, archive_path)
                break
            except urllib.error.HTTPError as exc:
                errors.append(f"{url} -> HTTP {exc.code}")
            except urllib.error.URLError as exc:
                errors.append(f"{url} -> {exc.reason}")
        else:
            message = ", ".join(errors) or f"Unable to locate ref '{ref}'"
            raise GithubDownloadError(
                f"Failed to download GitHub repo '{repo}' at ref '{ref}': {message}"
            )

        root_path = _extract_archive(archive_path, temp_dir)
        yield _resolve_subdir(root_path, subdir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
