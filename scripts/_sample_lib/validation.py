"""
Sample-YAML validation. Errors raise SampleError so the CLI wrapper
prints them with a single ERROR: prefix and exits non-zero.

`validate_sample` is the entry point: it sanity-checks the top-level
fields (schema_version, version, name, tagline, min_cli_version) and
then delegates to `validate_steps`, which in turn walks any
`deploy_agent` template to validate its `setup_requirements:` block.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

# RFC 4122 UUID — eight-four-four-four-twelve lowercase hex with dashes.
# Matches the format Python's `uuid.uuid4()` (used by the scaffold) emits
# and the format the Elixir `defconfig_object` field validator accepts.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_LOOKUP_KEY_RE = re.compile(r"^[a-z0-9_-]+$")

import yaml

from .paths import (
    CLI_VERSION_RE,
    ENV_VAR_KEY_RE,
    ENV_VAR_SCOPES,
    SAMPLE_SCHEMA_VERSION,
    SCRIPT_EXTENSIONS,
    SETUP_REQUIREMENT_KINDS,
    STEP_VERBS,
    VERSION_RE,
    display_path,
)


class SampleError(Exception):
    """Raised for any validation problem in a sample.yaml or its directory."""


def validate_sample(slug: str, raw: Any, source: pathlib.Path) -> dict[str, Any]:
    """
    Validate a sample.yaml. Errors point at source path + the offending key
    so a CI failure tells the author exactly where to look.
    """
    where = display_path(source)
    if not isinstance(raw, dict):
        raise SampleError(f"{where}: top-level must be a mapping, got {type(raw).__name__}")

    schema_version = raw.get("schema_version")
    if schema_version != SAMPLE_SCHEMA_VERSION:
        raise SampleError(
            f"{where}: schema_version must be {SAMPLE_SCHEMA_VERSION}, got {schema_version!r}. "
            f"If you're updating a sample from an earlier schema, bump schema_version to "
            f"{SAMPLE_SCHEMA_VERSION} and replace the old capabilities/deploy_mode fields "
            f"with a `steps:` block (see docs/ for the DSL reference)."
        )

    version = raw.get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise SampleError(
            f'{where}: version must be a string like "v1.2.3", got {version!r}'
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SampleError(f"{where}: name must be a non-empty string")

    tagline = raw.get("tagline")
    if not isinstance(tagline, str) or not tagline.strip():
        raise SampleError(f"{where}: tagline must be a non-empty string")

    min_cli_version = raw.get("min_cli_version")
    if not isinstance(min_cli_version, str) or not CLI_VERSION_RE.match(min_cli_version):
        raise SampleError(
            f'{where}: min_cli_version must be a string like "0.28.0", got {min_cli_version!r}'
        )

    # steps: is the new required block. `post_install:` is accepted as
    # an alias during the TS samples-catalog's transition, but we insist
    # on `steps:` in source of truth (sample.yaml) so authors converge
    # on one name.
    steps_raw = raw.get("steps")
    if steps_raw is None:
        raise SampleError(
            f"{where}: missing `steps:` block. Every sample must declare its "
            f"deploy sequence. See agents/code-review-agent/sample.yaml for the "
            f"simplest shape; the full DSL reference is in @archastro/samples-catalog."
        )
    validate_steps(slug, steps_raw, source)

    # Catalog-facing Solution wrapper is optional, but when present its
    # *_path fields must point at real files inside the sample dir and
    # its *_ref fields must resolve to local files by lookup_key. The
    # same local-file rule applies to markdown refs.
    validate_solution_yaml(source.parent)

    # Defensive check against authors leaving behind the old schema's
    # fields after migrating.
    for legacy_key in ("deploy_mode", "capabilities"):
        if legacy_key in raw:
            raise SampleError(
                f"{where}: `{legacy_key}` is from the old (schema_version: 1) "
                f"format and no longer has any effect — remove it. Deploy "
                f"behavior is now declared in `steps:`."
            )

    return {
        "slug": slug,
        "version": version,
        "name": name.strip(),
        "tagline": tagline.strip(),
        "min_cli_version": min_cli_version,
        "steps": steps_raw,
    }


def validate_steps(slug: str, steps: Any, source: pathlib.Path) -> None:
    """
    Shape-validate the `steps:` block. Catches obvious structural errors
    at packaging time; the TS executor does a full zod validation at
    runtime too, so this is the fast-feedback gate, not the safety net.

    Also reaches into the agent.yaml referenced by the `deploy_agent`
    step to validate its `setup_requirements:` block (mirrored from
    samples-catalog's schema.ts), cross-referencing custom verifier
    `script_ref` values against the lookup_keys an `upload_scripts`
    step would produce. Catches "verify.script_ref points at a script
    you forgot to ship" before it becomes a runtime install error.
    """
    where = display_path(source)
    if not isinstance(steps, list):
        raise SampleError(f"{where}: steps must be a list, got {type(steps).__name__}")

    # Each sample picks exactly one deploy verb — either `deploy_agent`
    # (creates a runtime agent) or `deploy_solution` (imports a catalog
    # Solution). Catches the "wrote all the scripts + skills, forgot to
    # deploy anything" mistake.
    deploy_count = 0
    sample_dir = source.parent

    # Collect script lookup_keys across every upload_scripts step so the
    # setup_requirements validator can cross-reference verify.script_ref.
    script_lookup_keys: set[str] = set()

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise SampleError(
                f"{where}: steps[{idx}] must be a mapping, got {type(step).__name__}"
            )
        verb = step.get("type")
        if verb not in STEP_VERBS:
            valid = ", ".join(sorted(STEP_VERBS))
            raise SampleError(
                f"{where}: steps[{idx}].type {verb!r} is not a known verb. "
                f"Valid verbs: {valid}."
            )

        spec = STEP_VERBS[verb]
        supplied = set(step.keys()) - {"type"}
        missing = spec["required"] - supplied
        if missing:
            raise SampleError(
                f"{where}: steps[{idx}] ({verb}) missing required fields: "
                f"{', '.join(sorted(missing))}"
            )
        unknown = supplied - spec["required"] - spec["optional"]
        if unknown:
            raise SampleError(
                f"{where}: steps[{idx}] ({verb}) has unknown fields: "
                f"{', '.join(sorted(unknown))}"
            )
        for field in supplied:
            value = step[field]
            if not isinstance(value, str) or not value.strip():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}).{field} must be a non-empty string, "
                    f"got {value!r}"
                )

        # Directory / file reality checks — catches `source_dir: skills`
        # on a sample that doesn't ship a skills/ subdirectory.
        if "source_dir" in step:
            target = sample_dir / step["source_dir"]
            if not target.is_dir():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}) source_dir "
                    f"{step['source_dir']!r} does not exist in {slug}/"
                )
        if "template_file" in step:
            target = sample_dir / step["template_file"]
            if not target.is_file():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}) template_file "
                    f"{step['template_file']!r} does not exist in {slug}/"
                )
        if "solution_file" in step:
            target = sample_dir / step["solution_file"]
            if not target.is_file():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}) solution_file "
                    f"{step['solution_file']!r} does not exist in {slug}/"
                )

        if verb == "upload_scripts":
            script_lookup_keys.update(_script_lookup_keys(sample_dir, step))

        if verb in ("deploy_agent", "deploy_solution"):
            deploy_count += 1

    if deploy_count != 1:
        raise SampleError(
            f"{where}: steps must contain exactly one deploy_agent or "
            f"deploy_solution step (found {deploy_count}). Every sample "
            f"picks exactly one deploy mode."
        )

    # upload_files attaches per-row files to a freshly-created agent's
    # installations — a deploy_agent-flow concept. The deploy_solution
    # flow publishes a library row (no agent → no installations →
    # nowhere to attach), so combining the two would silently drop
    # every upload_files step at install time. Mirrors the same
    # rejection in @archastro/samples-catalog's parseSteps.
    has_deploy_solution = any(
        isinstance(s, dict) and s.get("type") == "deploy_solution" for s in steps
    )
    upload_files_count = sum(
        1 for s in steps if isinstance(s, dict) and s.get("type") == "upload_files"
    )
    if has_deploy_solution and upload_files_count > 0:
        raise SampleError(
            f"{where}: upload_files is not supported alongside "
            f"deploy_solution (found {upload_files_count} upload_files "
            f"step(s)). Solution imports publish a library row; per-row "
            f"file attachments aren't part of that flow. Use deploy_agent "
            f"if you need post-install file uploads."
        )

    # Walk steps a second time to validate setup_requirements once we
    # know the full set of script lookup_keys (the deploy step might
    # appear before the upload_scripts step it depends on). Both
    # deploy_agent (template_file → agent.yaml directly) and
    # deploy_solution (solution_file → wrapped template via
    # template_path) resolve to an author-edited agent template.
    for idx, step in enumerate(steps):
        verb = step.get("type")
        if verb == "deploy_agent":
            template_path = sample_dir / step["template_file"]
            validate_setup_requirements(template_path, script_lookup_keys)
        elif verb == "deploy_solution":
            template_path = _resolve_wrapped_template(sample_dir, step)
            if template_path is not None:
                validate_setup_requirements(template_path, script_lookup_keys)


def _resolve_wrapped_template(
    sample_dir: pathlib.Path, step: dict[str, Any]
) -> pathlib.Path | None:
    """
    Resolve `solution.yaml.template.template_path` to the on-disk
    agent template so we can validate its setup_requirements. Returns
    None if the solution file is missing or doesn't reference a local
    template path (the dedicated solution validator surfaces those
    errors separately — here we just skip the deeper walk).
    """
    solution_path = sample_dir / step["solution_file"]
    if not solution_path.is_file():
        return None
    try:
        raw = yaml.safe_load(solution_path.read_text())
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    template = raw.get("template")
    if not isinstance(template, dict):
        return None
    path_ref = template.get("template_path")
    if isinstance(path_ref, str) and path_ref.strip():
        try:
            return _require_local_file(
                display_path(solution_path),
                sample_dir,
                sample_dir,
                path_ref,
                "template.template_path",
            )
        except SampleError:
            return None
    lookup_ref = template.get("template_ref")
    if not isinstance(lookup_ref, str) or not lookup_ref.strip():
        return None
    try:
        return _resolve_template_ref_file(
            display_path(solution_path),
            sample_dir,
            lookup_ref,
            "template.template_ref",
        )
    except SampleError:
        return None


def _script_lookup_keys(sample_dir: pathlib.Path, step: dict[str, Any]) -> set[str]:
    """
    Enumerate the lookup_keys an `upload_scripts` step would produce.
    Matches samples-catalog's `stripExtension(filename)` derivation.
    """
    source_dir = sample_dir / step["source_dir"]
    if not source_dir.is_dir():
        return set()
    # Accept either accepted script extension (.aascript or .agentscript).
    # The step's `glob:` (if any) decides what the executor actually
    # uploads at install time — this discovery is just for resolving
    # setup_requirements.verify.script_ref by file stem, so it's safe
    # (and helpful) to be permissive.
    keys: set[str] = set()
    for child in source_dir.iterdir():
        if child.is_file() and child.suffix in SCRIPT_EXTENSIONS:
            keys.add(child.stem)
    return keys


def validate_setup_requirements(
    agent_yaml_path: pathlib.Path, script_lookup_keys: set[str]
) -> None:
    """
    Validate the `setup_requirements:` block in an agent.yaml referenced
    by a `deploy_agent` step. Empty / absent block is fine — the field
    is optional.

    Mirrors the discriminated union in samples-catalog's schema.ts:
    env_var (key + scope + description, optional secret/example/etc.),
    install (installation_kind + description), custom (id + title +
    description + verify.script_ref).

    Cross-references custom `verify.script_ref` against the lookup_keys
    upload_scripts steps will produce — catches dangling references at
    packaging time instead of runtime.
    """
    try:
        raw = yaml.safe_load(agent_yaml_path.read_text())
    except yaml.YAMLError as exc:
        raise SampleError(
            f"{display_path(agent_yaml_path)}: invalid YAML — {exc}"
        )

    if not isinstance(raw, dict):
        # The deploy_agent template should be a mapping; if it isn't,
        # the install would fail anyway. Don't validate further.
        return

    requirements = raw.get("setup_requirements")
    if requirements is None:
        return

    where = display_path(agent_yaml_path)
    if not isinstance(requirements, list):
        raise SampleError(
            f"{where}: setup_requirements must be a list, got "
            f"{type(requirements).__name__}"
        )

    seen_ids: set[str] = set()
    for idx, req in enumerate(requirements):
        if not isinstance(req, dict):
            raise SampleError(
                f"{where}: setup_requirements[{idx}] must be a mapping, got "
                f"{type(req).__name__}"
            )

        kind = req.get("kind")
        if kind not in SETUP_REQUIREMENT_KINDS:
            valid = ", ".join(sorted(SETUP_REQUIREMENT_KINDS))
            raise SampleError(
                f"{where}: setup_requirements[{idx}].kind {kind!r} is not a known "
                f"kind. Valid kinds: {valid}."
            )

        spec = SETUP_REQUIREMENT_KINDS[kind]
        supplied = set(req.keys()) - {"kind"}
        missing = spec["required"] - supplied
        if missing:
            raise SampleError(
                f"{where}: setup_requirements[{idx}] ({kind}) missing required "
                f"fields: {', '.join(sorted(missing))}"
            )
        unknown = supplied - spec["required"] - spec["optional"]
        if unknown:
            raise SampleError(
                f"{where}: setup_requirements[{idx}] ({kind}) has unknown "
                f"fields: {', '.join(sorted(unknown))}"
            )

        identifier = _check_setup_requirement_shape(
            where, idx, kind, req, script_lookup_keys
        )

        if identifier in seen_ids:
            raise SampleError(
                f"{where}: setup_requirements[{idx}] duplicate identifier "
                f"{identifier!r} — env_var keys, install installation_kinds, and "
                f"custom ids must each be unique within the block."
            )
        seen_ids.add(identifier)

        depends_on = req.get("depends_on")
        if depends_on is not None and (
            not isinstance(depends_on, list)
            or not all(isinstance(x, str) for x in depends_on)
        ):
            raise SampleError(
                f"{where}: setup_requirements[{idx}].depends_on must be a list "
                f"of strings"
            )


def _check_setup_requirement_shape(
    where: str,
    idx: int,
    kind: str,
    req: dict[str, Any],
    script_lookup_keys: set[str],
) -> str:
    """
    Per-kind shape checks beyond the required/optional field list.
    Returns the entry's stable identifier (used for the dedupe check).
    """
    if kind == "env_var":
        key = req["key"]
        if not isinstance(key, str) or not ENV_VAR_KEY_RE.match(key):
            raise SampleError(
                f"{where}: setup_requirements[{idx}].key must be SCREAMING_SNAKE_CASE "
                f"(letters/numbers/underscores, starting with a letter), got {key!r}"
            )
        scope = req["scope"]
        if scope not in ENV_VAR_SCOPES:
            raise SampleError(
                f"{where}: setup_requirements[{idx}].scope {scope!r} is not a "
                f"valid scope. Valid scopes: {', '.join(sorted(ENV_VAR_SCOPES))}."
            )
        return key

    if kind == "install":
        installation_kind = req["installation_kind"]
        if not isinstance(installation_kind, str) or not installation_kind.strip():
            raise SampleError(
                f"{where}: setup_requirements[{idx}].installation_kind must be a "
                f"non-empty string"
            )
        return installation_kind

    # custom
    verify = req["verify"]
    if not isinstance(verify, dict):
        raise SampleError(
            f"{where}: setup_requirements[{idx}].verify must be a mapping, got "
            f"{type(verify).__name__}"
        )
    script_ref = verify.get("script_ref")
    if not isinstance(script_ref, str) or not script_ref.strip():
        raise SampleError(
            f"{where}: setup_requirements[{idx}].verify.script_ref must be a "
            f"non-empty string"
        )
    if script_lookup_keys and script_ref not in script_lookup_keys:
        raise SampleError(
            f"{where}: setup_requirements[{idx}].verify.script_ref {script_ref!r} "
            f"doesn't match any script in upload_scripts source_dir(s). "
            f"Available scripts: {', '.join(sorted(script_lookup_keys)) or '(none)'}."
        )
    identifier = req["id"]
    if not isinstance(identifier, str) or not identifier.strip():
        raise SampleError(
            f"{where}: setup_requirements[{idx}].id must be a non-empty string"
        )
    return identifier


# Inline Markdown image / link syntax: ![alt](href), [text](href),
# [text](href "title"). Reference-style ([text][id] paired with
# [id]: href elsewhere) is not handled — scaffolded README/readme
# blocks only use the inline form.
_MD_REF_RE = re.compile(
    r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?\s*(?:\"[^\"]*\"|'[^']*')?\s*\)"
)

# Anything starting with these is an off-disk reference we should not
# try to resolve to a local file.
_MD_NON_LOCAL_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "ftp://",
    "data:",
)


def validate_solution_yaml(sample_dir: pathlib.Path) -> None:
    """
    Validate solution.yaml (if present) for a single sample dir.

    Catalog-facing solutions reference bundled files either by path or
    by lookup key. `template_path` / `asset_path` values are paths
    relative to the bundle root and must resolve to real local files
    inside the sample dir. `template_ref` / `asset_ref` values are
    lookup-key refs and must resolve to real local files by basename
    lookup_key; path-like values belong in the corresponding *_path
    field.
    The same local-file rule applies to local image/link refs in the
    inline `readme:` markdown and in any `.md` files under the sample
    dir.

    Samples without solution.yaml are unchanged.
    """
    sol_path = sample_dir / "solution.yaml"
    if not sol_path.exists():
        return

    try:
        raw = yaml.safe_load(sol_path.read_text())
    except yaml.YAMLError as exc:
        raise SampleError(f"{display_path(sol_path)}: invalid YAML — {exc}")

    where = display_path(sol_path)
    if not isinstance(raw, dict):
        raise SampleError(f"{where}: top-level must be a mapping")

    lookup_key = raw.get("lookup_key")
    if not isinstance(lookup_key, str) or not lookup_key.strip():
        raise SampleError(
            f"{where}: missing or empty `lookup_key:` — every Solution must "
            f"declare a stable lookup_key (e.g. `<slug>-solution`) so the "
            f"catalog can address the imported row."
        )

    solution_id = raw.get("solution_id")
    if not isinstance(solution_id, str) or not _UUID_RE.match(solution_id):
        raise SampleError(
            f"{where}: missing or invalid `solution_id:` — must be a "
            f"lowercase RFC 4122 UUID (the scaffold mints one with "
            f"uuid.uuid4()). samples-catalog derives the per-import "
            f"`lookup_key_prefix` (`sol-<solution_id>`) and "
            f"`virtual_path_prefix` (`solution-bundle/<solution_id>`) "
            f"from this value."
        )

    # solution_version + name mirror the platform Solution config schema
    # (`ArchAstro.Config.Objects.Solution`) so a bundle that passes
    # validate here doesn't get rejected later by the Elixir defconfig
    # schema during /api/solutions/import.
    solution_version = raw.get("solution_version")
    if not isinstance(solution_version, str) or not VERSION_RE.match(solution_version):
        raise SampleError(
            f'{where}: missing or invalid `solution_version:` — must be a '
            f'string like "v1.2.3", got {solution_version!r}'
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SampleError(
            f"{where}: missing or empty `name:` — every Solution must "
            f"declare a non-empty display name shown in the catalog."
        )

    template = raw.get("template")
    if not isinstance(template, dict):
        raise SampleError(
            f"{where}: missing or invalid `template:` block — samples-catalog "
            f"requires `template_path:` or `template_ref:` for the wrapped "
            f"template file."
        )

    if "template_path" in template:
        template_path_value = template["template_path"]
        template_path = _require_local_file(
            where,
            sample_dir,
            sample_dir,
            template_path_value,
            "template.template_path",
        )
        _reject_agent_key_in_wrapped_template_at_path(
            where, template_path_value, template_path
        )
    elif "template_ref" in template:
        template_ref = template["template_ref"]
        template_path = _resolve_template_ref_file(
            where, sample_dir, template_ref, "template.template_ref"
        )
        _reject_agent_key_in_wrapped_template_at_path(
            where, template_ref, template_path
        )
    else:
        raise SampleError(
            f"{where}: `template:` must carry a non-empty `template_path:` "
            f"or `template_ref:` string. Inline templates are not supported "
            f"by samples-catalog."
        )

    # `assets:` is optional, but when present it must be a list. A
    # non-list value (e.g. a mapping the author wrote thinking they
    # were declaring a single asset) would otherwise silently drop
    # here and fail later at import time when the platform schema
    # rejects the body.
    if "assets" in raw:
        assets = raw["assets"]
        if not isinstance(assets, list):
            raise SampleError(
                f"{where}: `assets:` must be a list of `{{ asset_path: <path> }}` "
                f"or `{{ asset_ref: <lookup_key> }}` entries when present, "
                f"got {type(assets).__name__}. To ship a single asset, wrap it "
                f"in a list."
            )
        for idx, asset in enumerate(assets):
            if not isinstance(asset, dict):
                raise SampleError(
                    f"{where}: assets[{idx}] must be a mapping with "
                    f"`asset_path:` or `asset_ref:`, got "
                    f"{type(asset).__name__}"
                )
            if "asset_path" in asset:
                _require_local_file(
                    where,
                    sample_dir,
                    sample_dir,
                    asset["asset_path"],
                    f"assets[{idx}].asset_path",
                )
            elif "asset_ref" in asset:
                _resolve_asset_ref_file(
                    where, sample_dir, asset["asset_ref"], f"assets[{idx}].asset_ref"
                )
            else:
                raise SampleError(
                    f"{where}: assets[{idx}] must carry a non-empty "
                    f"`asset_path:` string or `asset_ref:` lookup key."
                )

    readme_md = raw.get("readme")
    if isinstance(readme_md, str):
        _validate_markdown_refs(sol_path, sample_dir, sample_dir, readme_md, label="readme:")

    for md_path in sorted(sample_dir.rglob("*.md")):
        _validate_markdown_refs(md_path, sample_dir, md_path.parent, md_path.read_text())


def _resolve_template_ref_file(
    where: str, sample_dir: pathlib.Path, template_ref: object, field: str
) -> pathlib.Path:
    lookup_key = _require_lookup_key_ref(where, template_ref, field, "template_path")
    return _find_unique_lookup_key_file(
        where,
        sample_dir / "agents",
        lookup_key,
        field,
        "template",
        suffixes={".yaml"},
    )


def _resolve_asset_ref_file(
    where: str, sample_dir: pathlib.Path, asset_ref: object, field: str
) -> pathlib.Path:
    lookup_key = _require_lookup_key_ref(where, asset_ref, field, "asset_path")
    return _find_unique_lookup_key_file(
        where,
        sample_dir,
        lookup_key,
        field,
        "asset",
        skip_names={".aaignore", "sample.yaml", "solution.yaml"},
    )


def _require_lookup_key_ref(
    where: str, value: Any, field: str, path_field: str
) -> str:
    _require_non_empty_string(where, value, field)
    assert isinstance(value, str)
    if not _LOOKUP_KEY_RE.match(value):
        raise SampleError(
            f"{where}: {field} {value!r} must be a lookup_key "
            f"(lowercase letters, numbers, underscores, or hyphens). "
            f"Use `{path_field}:` for bundle-relative file paths."
        )
    return value


def _find_unique_lookup_key_file(
    where: str,
    root: pathlib.Path,
    lookup_key: str,
    field: str,
    label: str,
    suffixes: set[str] | None = None,
    skip_names: set[str] | None = None,
) -> pathlib.Path:
    if not root.is_dir():
        raise SampleError(
            f"{where}: {field} {lookup_key!r} does not match any local "
            f"{label} file lookup_key."
        )

    skip_names = skip_names or set()
    candidates: list[pathlib.Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in skip_names:
            continue
        if suffixes is not None and path.suffix not in suffixes:
            continue
        if path.stem == lookup_key:
            candidates.append(path)

    if not candidates:
        raise SampleError(
            f"{where}: {field} {lookup_key!r} does not match any local "
            f"{label} file lookup_key."
        )
    if len(candidates) > 1:
        rels = ", ".join(
            sorted(p.relative_to(root).as_posix() for p in candidates)
        )
        raise SampleError(
            f"{where}: {field} {lookup_key!r} is ambiguous; multiple local "
            f"{label} files have that lookup_key: {rels}."
        )
    return candidates[0]


def _reject_agent_key_in_wrapped_template_at_path(
    where: str, template_label: str, template_path: pathlib.Path
) -> None:
    """
    Read the wrapped template body at `template_path` and raise if (a)
    it does not parse as a YAML mapping, or (b) it declares
    `agent_key:`.

    Parseability has to be checked here — otherwise a syntactically
    broken template body would slip past sample-time validation and
    detonate later when the platform parses it during import.
    """
    try:
        raw = yaml.safe_load(template_path.read_text())
    except yaml.YAMLError as exc:
        raise SampleError(
            f"{where}: wrapped template {template_label!r} did not parse as YAML — {exc}"
        )
    if not isinstance(raw, dict):
        raise SampleError(
            f"{where}: wrapped template {template_label!r} must be a YAML mapping, "
            f"got {type(raw).__name__}. Templates are top-level objects — check "
            f"for stray scalars or list-at-root."
        )
    if "agent_key" in raw:
        raise SampleError(
            f"{where}: wrapped template {template_label!r} declares "
            f"`agent_key:`, which is a deploy_agent-only field. Solution "
            f"import publishes a library row; no agent is provisioned, "
            f"so `agent_key` has no meaning here. Move the agent_key-bearing "
            f"template into a separate deploy_agent sample, or drop the field."
        )


def _require_non_empty_string(where: str, value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SampleError(
            f"{where}: {field} must be a non-empty string, got {value!r}"
        )


def _require_local_file(
    where: str,
    sample_dir: pathlib.Path,
    base_dir: pathlib.Path,
    value: Any,
    field: str,
) -> pathlib.Path:
    """
    Resolve `value` against `base_dir` and require it points at an
    existing regular file inside `sample_dir`. Used for template_path /
    asset_path and markdown image/link refs (base_dir == the markdown
    file's directory).
    """
    if not isinstance(value, str) or not value.strip():
        raise SampleError(
            f"{where}: {field} must be a non-empty string, got {value!r}"
        )
    if pathlib.PurePath(value).is_absolute():
        raise SampleError(
            f"{where}: {field} {value!r} must be a relative path "
            f"(paths are resolved against the sample directory)"
        )
    sample_root = sample_dir.resolve()
    resolved = (base_dir / value).resolve()
    try:
        resolved.relative_to(sample_root)
    except ValueError:
        raise SampleError(
            f"{where}: {field} {value!r} escapes the sample directory "
            f"(must point at a file inside {sample_root.name}/)"
        )
    if not resolved.is_file():
        raise SampleError(
            f"{where}: {field} {value!r} does not point at a real file "
            f"(expected {sample_root.name}/{resolved.relative_to(sample_root).as_posix()})"
        )
    return resolved


def _validate_markdown_refs(
    source: pathlib.Path,
    sample_dir: pathlib.Path,
    base_dir: pathlib.Path,
    text: str,
    label: str | None = None,
) -> None:
    where = f"{display_path(source)}" + (f" ({label})" if label else "")
    for match in _MD_REF_RE.finditer(text):
        ref = match.group(1).strip()
        if not ref or ref.startswith("#"):
            continue
        if any(ref.lower().startswith(prefix) for prefix in _MD_NON_LOCAL_PREFIXES):
            continue
        # Markdown allows #fragment / ?query suffixes; strip before
        # filesystem resolution.
        path_only = ref.split("#", 1)[0].split("?", 1)[0]
        if not path_only:
            continue
        _require_local_file(where, sample_dir, base_dir, path_only, f"markdown ref {ref!r}")
