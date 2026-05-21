"""
The `pack` subcommand: validate one sample and build its release
tarball locally. CI's release-samples.yml delegates here so there's
one definition of "the tarball" — same archive whether it comes from
`gh release` or a local `archastro install sample ./slug-vX.Y.Z.tar.gz`.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tarfile
from typing import Any

import yaml

from .paths import REPO_ROOT, SAMPLE_ROOTS
from .validation import SampleError, validate_sample


def _resolve_sample_dir(slug_or_path: str) -> tuple[str, pathlib.Path]:
    """
    Map the positional arg to (slug, sample_dir).

    Paths are cwd-relative or absolute and always win. A bare
    `my-sample` first resolves like `./my-sample`; if that path does
    not exist, fall back to looking for the slug under each
    SAMPLE_ROOTS entry (agents/, solutions/). Slug for tarball naming
    is the directory's basename.
    """
    expanded = pathlib.Path(slug_or_path).expanduser()
    cwd_candidate = expanded.resolve()
    if (
        cwd_candidate.exists()
        or expanded.is_absolute()
        or "/" in slug_or_path
        or "\\" in slug_or_path
        or slug_or_path.startswith(".")
    ):
        return cwd_candidate.name, cwd_candidate

    for root, _kind in SAMPLE_ROOTS:
        catalog_candidate = (root / slug_or_path).resolve()
        if catalog_candidate.exists():
            return catalog_candidate.name, catalog_candidate

    expanded = cwd_candidate
    return expanded.name, expanded


def _load_one_sample(slug: str, sample_dir: pathlib.Path) -> dict[str, Any]:
    if not sample_dir.is_dir():
        raise SampleError(
            f"{sample_dir} does not exist or is not a directory. "
            f"Pass a path to an existing sample directory, or scaffold "
            f"a new one with `uv run scripts/sample_tool.py new {slug}`."
        )
    yaml_path = sample_dir / "sample.yaml"
    if not yaml_path.exists():
        raise SampleError(
            f"{yaml_path} is missing. A sample needs a sample.yaml "
            f"before it can be packed."
        )
    raw = yaml.safe_load(yaml_path.read_text())
    return validate_sample(slug, raw, yaml_path)


def run_pack(slug_or_path: str, output_dir: pathlib.Path) -> int:
    slug, sample_dir = _resolve_sample_dir(slug_or_path)
    sample = _load_one_sample(slug, sample_dir)
    version = sample["version"]
    tarball = output_dir / f"{slug}-{version}.tar.gz"

    output_dir.mkdir(parents=True, exist_ok=True)

    # macOS hygiene: stop any child processes we shell out to (and any
    # macOS-aware file operations underneath) from emitting AppleDouble
    # `._<name>` companion files. Python's tarfile doesn't produce them
    # itself, but COPYFILE_DISABLE also stops them from being created
    # by `cp`/`mv`/`bsdtar` ops the author might run alongside `pack`,
    # and the env var is a cheap and well-known signal of intent.
    if sys.platform == "darwin":
        os.environ.setdefault("COPYFILE_DISABLE", "1")

    # arcname=slug matches the layout the GitHub Releases tarball uses
    # (`tar -C agents -czf <tarball> <slug>`), so the consumer doesn't
    # have to care which producer built it. Sort entries for a
    # deterministic-ish archive — Python's tarfile still embeds mtimes,
    # so this isn't bit-reproducible, but byte-stable layout is enough
    # for `archastro install sample` smoke tests.
    #
    # `._<name>` AppleDouble companions are skipped explicitly: macOS
    # creates them when files cross HFS+ ↔ non-HFS+ boundaries (SMB
    # shares, ExFAT/FAT32 USB drives, some Docker bind mounts). They
    # carry only extended attributes the platform doesn't read, and
    # extractors that don't strip them silently double-register every
    # config (and the platform's import error message for the
    # resulting duplicate is cryptic).
    with tarfile.open(tarball, "w:gz") as tar:
        for entry in sorted(sample_dir.rglob("*")):
            if _is_apple_double(entry):
                continue
            rel = entry.relative_to(sample_dir)
            arcname = f"{slug}/{rel.as_posix()}"
            tar.add(entry, arcname=arcname, recursive=False)

    try:
        display = tarball.relative_to(REPO_ROOT)
    except ValueError:
        display = tarball
    print(f"Wrote {display}", file=sys.stderr)
    return 0


def _is_apple_double(entry: pathlib.Path) -> bool:
    """
    True if `entry` is a macOS AppleDouble companion (`._<name>`) or
    one lives anywhere on its path. Walks the parents so a stray
    `._foo` directory doesn't smuggle its children into the tarball.
    """
    if entry.name.startswith("._"):
        return True
    for parent in entry.parents:
        if parent.name.startswith("._"):
            return True
    return False
