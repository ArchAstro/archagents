"""
The `generate` subcommand: load every sample under agents/ and
solutions/, validate them, then write each sample's .aaignore plus the top-level
samples.json. `--check` exits non-zero if any planned file would
differ from what's on disk — that's the CI gate.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import yaml

from .paths import MANIFEST_PATH, REPO_ROOT, SAMPLE_ROOTS
from .render import render_aaignore, render_manifest
from .validation import SampleError, validate_sample


def load_all_samples() -> list[dict[str, Any]]:
    """
    Walk every SAMPLE_ROOTS entry (agents/ and solutions/), treating
    each top-level subdirectory as a sample. Slugs must stay unique
    across roots — two samples with the same name in different roots
    would collide on the catalog row keyed by lookup_key/slug.
    """
    samples: list[dict[str, Any]] = []
    seen_slugs: dict[str, pathlib.Path] = {}
    for root in SAMPLE_ROOTS:
        if not root.is_dir():
            continue
        for sample_dir in sorted(root.iterdir()):
            if not sample_dir.is_dir():
                continue
            existing = seen_slugs.get(sample_dir.name)
            if existing is not None:
                raise SampleError(
                    f"slug {sample_dir.name!r} appears in both "
                    f"{existing.relative_to(REPO_ROOT)} and "
                    f"{sample_dir.relative_to(REPO_ROOT)}. Slugs must be "
                    f"unique across agents/ and solutions/."
                )
            yaml_path = sample_dir / "sample.yaml"
            if not yaml_path.exists():
                raise SampleError(
                    f"{sample_dir.relative_to(REPO_ROOT)}: missing sample.yaml. "
                    f"Every sample directory must declare its version + DSL steps."
                )
            raw = yaml.safe_load(yaml_path.read_text())
            sample = validate_sample(sample_dir.name, raw, yaml_path)
            # Stamp the discovery root so plan_outputs writes .aaignore
            # back to the right directory (samples can live under either
            # agents/ or solutions/).
            sample["sample_dir"] = sample_dir
            samples.append(sample)
            seen_slugs[sample_dir.name] = sample_dir
    if not samples:
        roots = ", ".join(str(r.relative_to(REPO_ROOT)) for r in SAMPLE_ROOTS)
        raise SampleError(f"No samples found under {roots}")
    return samples


def plan_outputs(samples: list[dict[str, Any]]) -> dict[pathlib.Path, str]:
    """
    Map each output path to the body we'd write. Used by both the
    write path and the --check drift comparator.
    """
    planned: dict[pathlib.Path, str] = {}
    for sample in samples:
        sample_dir = sample["sample_dir"]
        planned[sample_dir / ".aaignore"] = render_aaignore(sample_dir)
    planned[MANIFEST_PATH] = render_manifest(samples)
    return planned


def run_generate(check: bool) -> int:
    samples = load_all_samples()
    samples.sort(key=lambda s: s["slug"])
    planned = plan_outputs(samples)

    if check:
        return check_drift(planned)

    for path, body in planned.items():
        write_if_changed(path, body)
    return 0


def write_if_changed(path: pathlib.Path, body: str) -> None:
    """Only write when the content would change — keeps mtimes stable for tar."""
    if path.exists() and path.read_text() == body:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def check_drift(planned: dict[pathlib.Path, str]) -> int:
    drifted: list[pathlib.Path] = []
    for path, body in planned.items():
        if not path.exists() or path.read_text() != body:
            drifted.append(path)
    if not drifted:
        return 0
    print(
        "The following files are out of date. Run:\n"
        "    uv run scripts/sample_tool.py generate\n"
        "and commit the result.\n",
        file=sys.stderr,
    )
    for path in drifted:
        print(f"  - {path.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 1
