"""
The `pack` subcommand: validate one sample and build its release
tarball locally. CI's release-samples.yml delegates here so there's
one definition of "the tarball" — same archive whether it comes from
`gh release` or a local `archastro install sample ./slug-vX.Y.Z.tar.gz`.
"""
from __future__ import annotations

import pathlib
import sys
import tarfile
from typing import Any

import yaml

from .paths import REPO_ROOT
from .validation import SampleError, validate_sample


def _resolve_sample_dir(slug_or_path: str) -> tuple[str, pathlib.Path]:
    """
    Map the positional arg to (slug, sample_dir).

    Always cwd-relative — the tool doesn't know which catalog the user
    cares about. A bare `my-sample` resolves to `./my-sample`, exactly
    like every other shell command. From the archagents repo root,
    `pack agents/code-review-agent` is the catalog form; from anywhere
    else, just point at the directory directly. Slug for tarball
    naming is the directory's basename.
    """
    expanded = pathlib.Path(slug_or_path).expanduser().resolve()
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

    # arcname=slug matches the layout the GitHub Releases tarball uses
    # (`tar -C agents -czf <tarball> <slug>`), so the consumer doesn't
    # have to care which producer built it. Sort entries for a
    # deterministic-ish archive — Python's tarfile still embeds mtimes,
    # so this isn't bit-reproducible, but byte-stable layout is enough
    # for `archastro install sample` smoke tests.
    with tarfile.open(tarball, "w:gz") as tar:
        for entry in sorted(sample_dir.rglob("*")):
            rel = entry.relative_to(sample_dir)
            arcname = f"{slug}/{rel.as_posix()}"
            tar.add(entry, arcname=arcname, recursive=False)

    try:
        display = tarball.relative_to(REPO_ROOT)
    except ValueError:
        display = tarball
    print(f"Wrote {display}", file=sys.stderr)
    return 0
