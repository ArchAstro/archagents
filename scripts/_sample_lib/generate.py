"""
The `generate` subcommand: load every sample under agents/, validate
them, then write each sample's .aaignore plus the top-level
samples.json. `--check` exits non-zero if any planned file would
differ from what's on disk — that's the CI gate.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import yaml

from .paths import AGENTS_DIR, MANIFEST_PATH, REPO_ROOT
from .render import render_aaignore, render_manifest
from .validation import SampleError, validate_sample


def load_all_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for sample_dir in sorted(AGENTS_DIR.iterdir()):
        if not sample_dir.is_dir():
            continue
        yaml_path = sample_dir / "sample.yaml"
        if not yaml_path.exists():
            raise SampleError(
                f"{sample_dir.relative_to(REPO_ROOT)}: missing sample.yaml. "
                f"Every sample directory must declare its version + DSL steps."
            )
        raw = yaml.safe_load(yaml_path.read_text())
        sample = validate_sample(sample_dir.name, raw, yaml_path)
        samples.append(sample)
    if not samples:
        raise SampleError(f"No samples found under {AGENTS_DIR}")
    return samples


def plan_outputs(samples: list[dict[str, Any]]) -> dict[pathlib.Path, str]:
    """
    Map each output path to the body we'd write. Used by both the
    write path and the --check drift comparator.
    """
    planned: dict[pathlib.Path, str] = {}
    for sample in samples:
        sample_dir = AGENTS_DIR / sample["slug"]
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
