"""
The `lint` subcommand: walk every sample (or one slug) and surface
best-practice warnings the strict validator deliberately doesn't fail
on. Backend accepts these omissions; lint nudges authors toward
catalog-ready samples without breaking existing ones.

Warnings cover:
  * solution.yaml `category_keys` (at least one) so the Library
    carousel can shelf the bundle.
  * solution.yaml `tag_keys` (at least one) so search + filter pickers
    surface the bundle.
  * solution.yaml `description` (catalog tagline) and either inline
    `readme:` or per-template `readme_path:` so the inspector renders
    long-form copy instead of a fallback placeholder.
  * Sample dir root README.md so the GitHub view + the sample-source
    explorer have something to render.

`lint` exits 0 by default — warnings only. `--strict` flips that to
non-zero on any warning so CI can opt in once a sample is clean.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from typing import Any

import yaml

from .paths import REPO_ROOT, SAMPLE_ROOTS, display_path


@dataclass(frozen=True)
class LintWarning:
    """One best-practice issue. `where` is the sample-relative source
    path so the CLI output is greppable + clickable."""

    slug: str
    where: str
    message: str


def run_lint(slug: str | None, strict: bool) -> int:
    """
    Walk every sample under SAMPLE_ROOTS (agents/ + solutions/, in
    order) — or just one slug when provided — and print every best-
    practice warning. Returns 0 unless `strict` is set and at least
    one warning fired.
    """
    sample_dirs = _resolve_sample_dirs(slug)
    if not sample_dirs:
        roots = ", ".join(str(r.relative_to(REPO_ROOT)) for r in SAMPLE_ROOTS)
        print(f"lint: no samples found under {roots}", file=sys.stderr)
        return 1

    warnings: list[LintWarning] = []
    for sample_dir in sample_dirs:
        warnings.extend(_lint_sample(sample_dir))

    if not warnings:
        print(
            f"lint: clean ({len(sample_dirs)} sample(s) checked).",
            file=sys.stderr,
        )
        return 0

    for warning in warnings:
        print(
            f"WARN {warning.slug}: {warning.where}: {warning.message}",
            file=sys.stderr,
        )
    print(
        f"lint: {len(warnings)} warning(s) across "
        f"{len(sample_dirs)} sample(s).",
        file=sys.stderr,
    )
    return 1 if strict else 0


def _resolve_sample_dirs(slug: str | None) -> list[pathlib.Path]:
    if slug is not None:
        for root in SAMPLE_ROOTS:
            target = root / slug
            if target.is_dir():
                return [target]
        roots = ", ".join(str(r.relative_to(REPO_ROOT)) for r in SAMPLE_ROOTS)
        print(
            f"lint: {slug!r} is not a sample under {roots}",
            file=sys.stderr,
        )
        return []
    return [
        d
        for root in SAMPLE_ROOTS
        if root.is_dir()
        for d in sorted(root.iterdir())
        if d.is_dir()
    ]


def _lint_sample(sample_dir: pathlib.Path) -> list[LintWarning]:
    slug = sample_dir.name
    warnings: list[LintWarning] = []

    readme = sample_dir / "README.md"
    if not readme.is_file():
        warnings.append(
            LintWarning(
                slug,
                f"{slug}/",
                "missing README.md at the sample root — authors browsing "
                "on GitHub land on an empty directory.",
            )
        )

    sol_path = sample_dir / "solution.yaml"
    if sol_path.is_file():
        warnings.extend(_lint_solution(slug, sample_dir, sol_path))

    return warnings


def _lint_solution(
    slug: str, sample_dir: pathlib.Path, sol_path: pathlib.Path
) -> list[LintWarning]:
    where = display_path(sol_path)
    try:
        raw = yaml.safe_load(sol_path.read_text())
    except yaml.YAMLError:
        # The strict validator already surfaces parse errors with a
        # pointed message — don't double-report here.
        return []
    if not isinstance(raw, dict):
        return []

    warnings: list[LintWarning] = []

    if not _has_non_empty_list(raw.get("category_keys")):
        warnings.append(
            LintWarning(
                slug,
                where,
                "`category_keys:` is empty or missing — Library carousels "
                "shelf bundles by category. Add at least one taxonomy key "
                "(e.g. `category_keys: [operations]`).",
            )
        )

    if not _has_non_empty_list(raw.get("tag_keys")):
        warnings.append(
            LintWarning(
                slug,
                where,
                "`tag_keys:` is empty or missing — tag filters surface "
                "bundles by capability. Add at least one tag (e.g. "
                "`tag_keys: [slack, on-call]`).",
            )
        )

    if not _has_non_empty_string(raw.get("description")):
        warnings.append(
            LintWarning(
                slug,
                where,
                "`description:` is empty or missing — the Library card "
                "tagline falls back to the bundle name alone.",
            )
        )

    has_inline_readme = _has_non_empty_string(raw.get("readme"))
    template_entries = _templates_list(raw)
    template_count = len(template_entries)
    templates_with_readme = sum(
        1 for entry in template_entries if _entry_has_readme(entry)
    )

    # No coverage anywhere → the inspector renders a placeholder. If
    # there's a top-level readme: it covers every template's fallback,
    # so we don't nag per-entry. If only SOME templates declare
    # readme_path: (and no global fallback), call out the gaps so the
    # author either fills them in or sets a shared readme.
    if not has_inline_readme and templates_with_readme == 0:
        warnings.append(
            LintWarning(
                slug,
                where,
                "no `readme:` on the Solution and no `readme_path:` on "
                "any of its templates — the Library inspector renders a "
                "placeholder. Set the top-level `readme:` for shared copy "
                "or per-template `readme_path:` entries for tool/routine "
                "specifics.",
            )
        )
    elif not has_inline_readme and templates_with_readme < template_count:
        for idx, entry in enumerate(template_entries):
            if _entry_has_readme(entry):
                continue
            warnings.append(
                LintWarning(
                    slug,
                    where,
                    f"templates[{idx}] has no `readme_path:` and the "
                    f"Solution has no top-level `readme:` — the inspector "
                    f"renders a placeholder for this template. Add a "
                    f"`readme_path:` or set the shared `readme:`.",
                )
            )

    return warnings


def _templates_list(raw: dict[str, Any]) -> list[Any]:
    """Pull whatever `templates:` (or legacy `template:`) holds out of
    the solution body as a list. Don't validate shape here — strict
    validation already rejects misformed entries."""
    if isinstance(raw.get("templates"), list):
        return raw["templates"]
    if "template" in raw:
        return [raw["template"]]
    return []


def _entry_has_readme(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    return _has_non_empty_string(entry.get("readme_path"))


def _has_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(
        isinstance(item, str) and item.strip() for item in value
    )


def _has_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
