"""
Semantic validation of sample .aascript files via the archagent CLI.

The CLI delegates the actual parse/validate work to the production
platform runtime, so this module is a thin orchestrator: discover
every script referenced by every sample's `upload_scripts` steps,
then shell out one `archagent validate script --file <path>` per
script and aggregate results.

Lives in CI under .github/workflows/validate-sample-scripts.yml,
which checks out the validator from a trusted ref and points it at
an untrusted "sample-source" tree via `--repo-root`. The defensive
symlink + parent-traversal checks below exist because the data
that walks through this code is hostile by assumption — never
follow a symlink, never resolve outside the sample directory.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from typing import Any

import yaml

LITERAL_EXTENSION_GLOB_RE = re.compile(r"^\*(\.[A-Za-z0-9]+)$")
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 60

Runner = Callable[..., subprocess.CompletedProcess[str]]


class SampleScriptValidationError(RuntimeError):
    """Raised for any structural or filesystem problem encountered while
    enumerating scripts to hand to the CLI. Kept separate from the
    yaml-shape SampleError because the failure modes (timeouts,
    subprocess returncodes, malicious symlinks) don't overlap."""


def _load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SampleScriptValidationError(f"{path}: invalid YAML: {exc}") from exc


def _script_match_extension(pattern: str | None) -> str | None:
    if pattern is None:
        return ".aascript"
    match = LITERAL_EXTENSION_GLOB_RE.match(pattern)
    return match.group(1) if match else None


def _safe_source_dir(sample_dir: pathlib.Path, source_dir_value: str) -> pathlib.Path:
    source_path = pathlib.PurePosixPath(source_dir_value.replace(os.sep, "/"))
    if source_path.is_absolute() or ".." in source_path.parts:
        raise SampleScriptValidationError(
            f"{sample_dir / 'sample.yaml'}: source_dir {source_dir_value!r} must stay inside the sample directory"
        )

    source_dir = sample_dir / source_dir_value
    if source_dir.is_symlink():
        raise SampleScriptValidationError(
            f"{sample_dir / 'sample.yaml'}: source_dir {source_dir_value!r} must not be a symlink"
        )
    if not source_dir.is_dir():
        raise SampleScriptValidationError(
            f"{sample_dir / 'sample.yaml'}: source_dir {source_dir_value!r} does not exist"
        )

    resolved_sample = sample_dir.resolve()
    resolved_source = source_dir.resolve()
    if not resolved_source.is_relative_to(resolved_sample):
        raise SampleScriptValidationError(
            f"{sample_dir / 'sample.yaml'}: source_dir {source_dir_value!r} must stay inside the sample directory"
        )
    return source_dir


def _sample_yaml_paths(repo_root: pathlib.Path) -> list[pathlib.Path]:
    agents_dir = repo_root / "agents"
    if agents_dir.is_symlink():
        raise SampleScriptValidationError(f"{agents_dir}: agents directory must not be a symlink")
    if not agents_dir.is_dir():
        raise SampleScriptValidationError(f"{agents_dir}: agents directory not found")

    resolved_agents = agents_dir.resolve()
    resolved_repo = repo_root.resolve()
    if not resolved_agents.is_relative_to(resolved_repo):
        raise SampleScriptValidationError(f"{agents_dir}: agents directory must stay inside the repository")

    paths: list[pathlib.Path] = []
    for sample_dir in sorted(agents_dir.iterdir()):
        if sample_dir.is_symlink():
            raise SampleScriptValidationError(f"{sample_dir}: sample directory must not be a symlink")
        if not sample_dir.is_dir():
            continue
        if not sample_dir.resolve().is_relative_to(resolved_agents):
            raise SampleScriptValidationError(f"{sample_dir}: sample directory must stay inside agents/")

        sample_yaml = sample_dir / "sample.yaml"
        if not sample_yaml.exists():
            continue
        if sample_yaml.is_symlink():
            raise SampleScriptValidationError(f"{sample_yaml}: sample.yaml must not be a symlink")
        if not sample_yaml.is_file():
            raise SampleScriptValidationError(f"{sample_yaml}: sample.yaml must be a regular file")
        if not sample_yaml.resolve().is_relative_to(sample_dir.resolve()):
            raise SampleScriptValidationError(f"{sample_yaml}: sample.yaml must stay inside the sample directory")
        paths.append(sample_yaml)
    return paths


def _safe_script_matches(
    sample_dir: pathlib.Path,
    source_dir: pathlib.Path,
    pattern: str | None,
) -> list[pathlib.Path]:
    resolved_sample = sample_dir.resolve()
    match_ext = _script_match_extension(pattern)
    safe_matches: list[pathlib.Path] = []
    for match in sorted(source_dir.rglob("*")):
        if match.is_symlink() or not match.is_file():
            continue
        resolved_match = match.resolve()
        if not resolved_match.is_relative_to(resolved_sample):
            raise SampleScriptValidationError(
                f"{match}: upload_scripts must not match outside {sample_dir}"
            )
        relative_name = match.relative_to(source_dir).as_posix()
        if match_ext is not None and not relative_name.endswith(match_ext):
            continue
        safe_matches.append(match)
    return safe_matches


def discover_sample_script_files(repo_root: pathlib.Path) -> list[pathlib.Path]:
    scripts: set[pathlib.Path] = set()
    for sample_yaml in _sample_yaml_paths(repo_root):
        sample = _load_yaml(sample_yaml)
        if not isinstance(sample, dict):
            raise SampleScriptValidationError(f"{sample_yaml}: sample.yaml must be a mapping")

        steps = sample.get("steps", [])
        if not isinstance(steps, list):
            raise SampleScriptValidationError(f"{sample_yaml}: steps must be a list")

        sample_dir = sample_yaml.parent
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                raise SampleScriptValidationError(
                    f"{sample_yaml}: steps[{idx}] must be a mapping"
                )
            if step.get("type") != "upload_scripts":
                continue

            source_dir_value = step.get("source_dir")
            if not isinstance(source_dir_value, str) or not source_dir_value.strip():
                raise SampleScriptValidationError(
                    f"{sample_yaml}: steps[{idx}].source_dir must be a non-empty string"
                )

            glob_value = step.get("glob")
            if glob_value is not None and (
                not isinstance(glob_value, str) or not glob_value.strip()
            ):
                raise SampleScriptValidationError(
                    f"{sample_yaml}: steps[{idx}].glob must be a non-empty string"
                )

            source_dir = _safe_source_dir(sample_dir, source_dir_value)
            scripts.update(_safe_script_matches(sample_dir, source_dir, glob_value))

    return sorted(scripts)


def _write_stream(stream: str | bytes | None, *, stderr: bool = False) -> None:
    if not stream:
        return
    if isinstance(stream, bytes):
        stream = stream.decode(errors="replace")
    target = sys.stderr if stderr else sys.stdout
    target.write(stream)
    if not stream.endswith("\n"):
        target.write("\n")


def _validation_json_failed(stdout: str) -> bool:
    if not stdout.strip():
        return False
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("valid") is False or payload.get("ok") is False


def validate_scripts(
    script_paths: Sequence[pathlib.Path],
    repo_root: pathlib.Path,
    cli: str = "archagent",
    runner: Runner = subprocess.run,
    timeout_seconds: int = DEFAULT_SCRIPT_TIMEOUT_SECONDS,
) -> int:
    failures: list[str] = []

    if not script_paths:
        print("No sample scripts found.")
        return 0

    with tempfile.TemporaryDirectory(prefix="archagents-script-validation-") as cwd:
        cli_cwd = pathlib.Path(cwd)
        for script_path in script_paths:
            rel_path = script_path.relative_to(repo_root).as_posix()
            print(f"Validating {rel_path}")
            try:
                result = runner(
                    [
                        cli,
                        "--output",
                        "json",
                        "validate",
                        "script",
                        "--file",
                        str(script_path.resolve()),
                    ],
                    cwd=cli_cwd,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                print(
                    f"Validation timed out after {timeout_seconds}s for {rel_path}",
                    file=sys.stderr,
                )
                _write_stream(exc.stdout)
                _write_stream(exc.stderr, stderr=True)
                failures.append(rel_path)
                continue

            validation_failed = result.returncode != 0 or _validation_json_failed(result.stdout)
            if validation_failed:
                _write_stream(result.stdout)
                _write_stream(result.stderr, stderr=True)
                failures.append(rel_path)

    if failures:
        print("\nScript validation failed for:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"Validated {len(script_paths)} sample script(s).")
    return 0


def run_validate(
    repo_root: pathlib.Path,
    cli: str,
    timeout_seconds: int,
) -> int:
    """CLI dispatch entrypoint used by sample_tool.py."""
    if timeout_seconds <= 0:
        print("--timeout-seconds must be positive", file=sys.stderr)
        return 1
    try:
        scripts = discover_sample_script_files(repo_root.resolve())
    except SampleScriptValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return validate_scripts(scripts, repo_root.resolve(), cli, timeout_seconds=timeout_seconds)
