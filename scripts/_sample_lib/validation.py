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
    DISPLAY_NAME_REQUIRED_KINDS,
    ENV_VAR_KEY_RE,
    ENV_VAR_SCOPES,
    SAMPLE_SCHEMA_VERSION,
    SCRIPT_EXTENSIONS,
    SETUP_ACTIONS_KINDS,
    SETUP_ACTION_TYPES,
    SETUP_REQUIREMENT_KINDS,
    STEP_VERBS,
    TEMPLATE_DESCRIPTION_REQUIRED_KINDS,
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
            f"deploy sequence. See solutions/code-review-agent-sample/sample.yaml for the "
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
    # deploy_solution (solution_file → bundled templates) resolve to
    # author-edited agent template files. A solution bundle may carry
    # multiple templates; each is walked independently.
    for idx, step in enumerate(steps):
        verb = step.get("type")
        if verb == "deploy_agent":
            template_path = sample_dir / step["template_file"]
            validate_template_metadata(template_path)
            validate_setup_requirements(template_path, script_lookup_keys)
        elif verb == "deploy_solution":
            for template_path in _resolve_wrapped_templates(sample_dir, step):
                validate_setup_requirements(template_path, script_lookup_keys)

    # Finally, dedupe lookup_keys across every artifact this bundle
    # ships. The platform's per-(app, org, sandbox) config namespace is
    # flat across kinds — a Script and an AgentToolTemplate sharing a
    # lookup_key collide at import time with a 422, even though they
    # resolve as separate config rows. Catch up front so a bundle that
    # passes validate is also a bundle the import endpoint will accept.
    _validate_bundle_lookup_key_uniqueness(steps, sample_dir, source)


def _validate_bundle_lookup_key_uniqueness(
    steps: list[dict[str, Any]],
    sample_dir: pathlib.Path,
    source: pathlib.Path,
) -> None:
    """
    Reject any lookup_key reused across artifacts in this sample's
    bundle.

    Mirrors the platform's `InstallPrimitives.derive_lookup_key/2`
    (src/elixir/core/lib/solutions/install_primitives.ex): the body's
    `lookup_key:` field wins when declared; otherwise identity falls
    back to the filename stem (basename without extension). Once the
    platform namespaces every entry with the bundle's
    `sol-<solution_id>-` prefix, two artifacts sharing a derived key
    land in the same `(app_id, lookup_key, sandbox_id, org_id)` slot
    on the `configs_lookup_key_unique_index` and the second one
    fails the INSERT inside the import transaction.

    Artifacts checked:
      * Every `upload_scripts` source_dir entry (lookup_key = filename
        stem; scripts are aascript text with no YAML body so they
        never declare an explicit lookup_key).
      * The `deploy_agent` template_file (body's explicit `lookup_key:`
        when set, else filename stem — same precedence the platform
        uses now).
      * Every template body in a `deploy_solution`'s
        `solution.yaml.templates:` list (same precedence).

    The earlier "explicit-only" stance let a sample author ship a
    tool YAML alongside a script with the same stem (e.g.
    `tools/foo.yaml` + `scripts/foo.aascript`); the validator saw two
    different declared/derived keys and passed, but the platform's
    stem-only derivation collapsed them and the import returned a
    422 on `configs_lookup_key_unique_index`. Falling back to the
    stem here keeps the validator honest about the platform's actual
    namespace flatness.
    """
    where = display_path(source)
    owners: dict[str, str] = {}

    def register(key: str, owner: str) -> None:
        existing = owners.get(key)
        if existing is not None and existing != owner:
            raise SampleError(
                f"{where}: lookup_key {key!r} is used by two bundle "
                f"artifacts: {existing} and {owner}. The platform's "
                f"per-(app, org, sandbox) config namespace is flat "
                f"across kinds, so both collide on the "
                f"`configs_lookup_key_unique_index` at import time. "
                f"Fix by either (a) declaring an explicit, distinct "
                f"`lookup_key:` in the template's body — e.g. "
                f"`lookup_key: arc-tool-{key}` on an AgentToolTemplate, "
                f"`arc-routine-{key}` on an AgentRoutineTemplate — or "
                f"(b) renaming one of the colliding files so the "
                f"stems differ."
            )
        owners[key] = owner

    for step in steps:
        if not isinstance(step, dict):
            continue
        verb = step.get("type")
        if verb == "upload_scripts":
            source_dir_rel = step.get("source_dir")
            if not isinstance(source_dir_rel, str):
                continue
            source_dir_abs = sample_dir / source_dir_rel
            if not source_dir_abs.is_dir():
                continue
            for child in sorted(source_dir_abs.iterdir()):
                if child.is_file() and child.suffix in SCRIPT_EXTENSIONS:
                    register(
                        child.stem,
                        f"Script {source_dir_rel}/{child.name}",
                    )
        elif verb == "deploy_agent":
            template_file = step.get("template_file")
            if isinstance(template_file, str):
                _register_template_lookup_key(
                    sample_dir / template_file, template_file, register
                )
        elif verb == "deploy_solution":
            sample_root = sample_dir.resolve()
            for template_path in _resolve_wrapped_templates(sample_dir, step):
                # _require_local_file calls .resolve(); on macOS that
                # rewrites /var/folders/... → /private/var/folders/...
                # via the standard tempfile symlink. Resolve both sides
                # so .relative_to() doesn't trip over that rewrite.
                rel = template_path.resolve().relative_to(sample_root).as_posix()
                _register_template_lookup_key(template_path, rel, register)


def _register_template_lookup_key(
    template_path: pathlib.Path,
    rel: str,
    register: Any,
) -> None:
    """Read a template body's kind + lookup_key and register with the
    caller's collision-detecting closure. Mirrors the platform's
    `derive_lookup_key/2` precedence (body's `lookup_key:` wins, else
    filename stem)."""
    declared_key: str | None = None
    kind = "Template"
    try:
        raw = yaml.safe_load(template_path.read_text())
    except (OSError, yaml.YAMLError):
        # Parse failures surface in the dedicated YAML validator; here
        # we only need the stem-fallback identity.
        raw = None
    if isinstance(raw, dict):
        candidate = raw.get("lookup_key")
        if isinstance(candidate, str) and candidate.strip():
            declared_key = candidate.strip()
        raw_kind = raw.get("kind")
        if isinstance(raw_kind, str) and raw_kind.strip():
            kind = raw_kind.strip()

    key = declared_key or template_path.stem
    register(key, f"{kind} {rel}")


def _resolve_wrapped_templates(
    sample_dir: pathlib.Path, step: dict[str, Any]
) -> list[pathlib.Path]:
    """
    Resolve every template entry in `solution.yaml`'s canonical
    `templates:` list (singular `template:` is normalized to a
    one-element list) to its on-disk agent template, so we can walk
    each one's setup_requirements. Returns an empty list when the
    solution file is missing or doesn't reference any local template —
    the dedicated solution validator surfaces those errors separately;
    here we just skip the deeper walk.
    """
    solution_path = sample_dir / step["solution_file"]
    if not solution_path.is_file():
        return []
    try:
        raw = yaml.safe_load(solution_path.read_text())
    except yaml.YAMLError:
        return []
    if not isinstance(raw, dict):
        return []
    try:
        entries = _normalize_template_entries(display_path(solution_path), raw)
    except SampleError:
        return []
    resolved: list[pathlib.Path] = []
    where = display_path(solution_path)
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        field_prefix = f"templates[{idx}]"
        path_ref = entry.get("template_path")
        if isinstance(path_ref, str) and path_ref.strip():
            try:
                resolved.append(
                    _require_local_file(
                        where,
                        sample_dir,
                        sample_dir,
                        path_ref,
                        f"{field_prefix}.template_path",
                    )
                )
            except SampleError:
                pass
            continue
        lookup_ref = entry.get("template_ref")
        if isinstance(lookup_ref, str) and lookup_ref.strip():
            try:
                resolved.append(
                    _resolve_template_ref_file(
                        where,
                        sample_dir,
                        lookup_ref,
                        f"{field_prefix}.template_ref",
                    )
                )
            except SampleError:
                pass
    return resolved


def _normalize_template_entries(where: str, raw: dict[str, Any]) -> list[Any]:
    """
    Pull the canonical templates list out of a solution.yaml mapping.

    Accepts either the canonical `templates: [<entry>, …]` shape or the
    legacy singular `template: <entry>` shape (normalized to a
    one-element list — mirrors `SolutionBundle.cast` on the wire side).
    Declaring both at once is rejected so authors don't end up with
    two sources of truth.

    Does not validate the entries themselves — that's the caller's
    job (validate_solution_yaml does the full per-entry walk).
    """
    has_singular = "template" in raw
    has_plural = "templates" in raw
    if has_singular and has_plural:
        raise SampleError(
            f"{where}: declare either `template:` or `templates:`, not both. "
            f"`templates:` is the canonical shape (a non-empty list); "
            f"`template:` is the legacy singular form, normalized to a "
            f"one-element list."
        )
    if has_plural:
        templates = raw["templates"]
        if not isinstance(templates, list) or not templates:
            raise SampleError(
                f"{where}: `templates:` must be a non-empty list of "
                f"`{{ template_path: <path> }}` or "
                f"`{{ template_ref: <lookup_key> }}` entries, "
                f"got {type(templates).__name__ if templates is not None else 'null'}."
            )
        return templates
    if has_singular:
        return [raw["template"]]
    return []


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


def validate_template_metadata(template_path: pathlib.Path) -> None:
    """
    Validate required top-level metadata on a deploy_agent template
    body. Solution-wrapped templates run the same metadata checks in
    `_validate_wrapped_template_body`; this covers regular agent
    samples that point directly at agent.yaml.
    """
    try:
        raw = yaml.safe_load(template_path.read_text())
    except yaml.YAMLError as exc:
        raise SampleError(
            f"{display_path(template_path)}: invalid YAML — {exc}"
        )
    if not isinstance(raw, dict):
        return
    _require_template_description(display_path(template_path), template_path.name, raw)


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

    Catalog-facing solutions bundle one or more templates under a
    canonical `templates:` list. Each entry references the on-disk
    template body either by `template_path` (relative file path) or
    `template_ref` (lookup_key resolved to a local *.yaml). The legacy
    singular `template:` shape is still accepted and normalized to a
    one-element list — mirrors the backend's `SolutionBundle.cast`
    behavior so local validation stays a superset of import.

    `asset_path` / `asset_ref` follow the same path-vs-lookup_key
    contract for any `assets:` entries. All `*_path` values must
    resolve to real local files inside the sample dir; all `*_ref`
    values must resolve to real local files by basename lookup_key.
    Per-template `readme_path:` (when declared) is held to the same
    `*_path` rule. The same local-file rule applies to local
    image/link refs in the inline `readme:` markdown and in any `.md`
    files under the sample dir.

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

    entries = _normalize_template_entries(where, raw)
    if not entries:
        raise SampleError(
            f"{where}: missing `templates:` list — every Solution must "
            f"bundle at least one template. Use `templates:` (canonical, "
            f"a non-empty list) or the legacy singular `template:` "
            f"(normalized to a one-element list at import time)."
        )

    seen_template_paths: set[pathlib.Path] = set()
    for idx, entry in enumerate(entries):
        field_prefix = f"templates[{idx}]"
        if not isinstance(entry, dict):
            raise SampleError(
                f"{where}: {field_prefix} must be a mapping with "
                f"`template_path:` or `template_ref:`, got "
                f"{type(entry).__name__}."
            )
        has_path = "template_path" in entry
        has_ref = "template_ref" in entry
        if has_path and has_ref:
            raise SampleError(
                f"{where}: {field_prefix} must declare either "
                f"`template_path:` or `template_ref:`, not both."
            )
        if has_path:
            template_path_value = entry["template_path"]
            template_path = _require_local_file(
                where,
                sample_dir,
                sample_dir,
                template_path_value,
                f"{field_prefix}.template_path",
            )
            _validate_wrapped_template_body(
                where, template_path_value, template_path
            )
        elif has_ref:
            template_ref = entry["template_ref"]
            template_path = _resolve_template_ref_file(
                where, sample_dir, template_ref, f"{field_prefix}.template_ref"
            )
            _validate_wrapped_template_body(
                where, template_ref, template_path
            )
        else:
            raise SampleError(
                f"{where}: {field_prefix} must carry a non-empty "
                f"`template_path:` or `template_ref:` string. Inline "
                f"templates are not supported by samples-catalog."
            )
        # Normalize via `.resolve()` so a path-mode and a ref-mode entry
        # that point at the same on-disk file collide here even though
        # they take different code paths above (one runs through
        # `.resolve()`, the other returns raw from `rglob`).
        resolved_template_path = template_path.resolve()
        if resolved_template_path in seen_template_paths:
            raise SampleError(
                f"{where}: {field_prefix} resolves to "
                f"{template_path.name!r}, already declared earlier in "
                f"`templates:`. Each template must appear once."
            )
        seen_template_paths.add(resolved_template_path)

        # `readme_path:` is optional, but when declared it must point
        # at a real bundle-relative file — the platform serves it via
        # the per-template signed `readme_url`, and samples-catalog
        # uploads the bytes from this path into `solution.files[]`. A
        # typo here only surfaces at install time as a missing readme
        # rendered as a placeholder; catching it locally fails the
        # author's pack step instead.
        if "readme_path" in entry:
            _require_local_file(
                where,
                sample_dir,
                sample_dir,
                entry["readme_path"],
                f"{field_prefix}.readme_path",
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


def _validate_wrapped_template_body(
    where: str, template_label: str, template_path: pathlib.Path
) -> None:
    """
    Read the wrapped template body at `template_path` and raise if:
      (a) it does not parse as a YAML mapping,
      (b) it declares `agent_key:` (deploy_agent-only field),
      (c) it is an AgentToolTemplate / AgentRoutineTemplate without a
          non-empty `display_name:` — the Library carousel and inspector
          render that label, and the backend's display fallbacks
          (humanize `name`) lose acronym casing (`query_osv` →
          `Query Osv` instead of `Query OSV`). Forcing samples to
          declare `display_name:` keeps the catalog presentation crisp,
          or
      (d) any inline `setup_actions:` entry is missing a non-empty
          `dedupe_key:`. Multi-template Solutions ship the same env_var
          or install action across the agent + every tool/routine that
          depends on it; without explicit dedupe_keys the post-install
          checklist double-counts. Source must declare dedupe so cross-
          template sharing is intentional and visible.

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
    kind = raw.get("kind")
    _require_template_description(where, template_label, raw)
    if kind in DISPLAY_NAME_REQUIRED_KINDS:
        display_name = raw.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"({kind}) must declare a non-empty `display_name:`. "
                f"`name:` is the machine-facing identifier (snake_case "
                f"for tools, kebab-case for routines); `display_name:` "
                f"is the human label rendered in the Library carousel "
                f"and inspector. Add e.g. `display_name: \"Query OSV.dev\"`."
            )
    if kind in SETUP_ACTIONS_KINDS:
        validate_setup_actions(where, template_label, raw)


def _require_template_description(
    where: str, template_label: str, raw: dict[str, Any]
) -> None:
    kind = raw.get("kind")
    if kind not in TEMPLATE_DESCRIPTION_REQUIRED_KINDS:
        return
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SampleError(
            f"{where}: template {template_label!r} ({kind}) must declare "
            f"a non-empty `description:`. Template descriptions are shown "
            f"beside standalone agent, tool, and routine rows in the Library."
        )


def validate_setup_actions(
    where: str, template_label: str, raw: dict[str, Any]
) -> None:
    """
    Validate the inline `setup_actions:` block on an AgentTemplate /
    AgentToolTemplate / AgentRoutineTemplate body. Empty / absent block
    is fine — the field is optional and an empty list is the explicit
    "no setup needed" shape.

    Each entry must declare:
      * `action_type:` (env_var | install | custom)
      * `title:`, `description:` — both non-empty strings
      * `params:` — kind-specific mapping (key/scope, installation_kind,
        or id)
      * `verify_config:` — kind-specific mapping
      * `dedupe_key:` — non-empty string. The platform uses
        (agent, dedupe_key) as a unique constraint on
        `agent_health_actions`, so two templates that ship the same
        env_var or install action should share a dedupe_key (one
        checklist row); two distinct actions should pick distinct keys.

    Optional fields: `required:` (bool), `sort_order:` (int),
    `depends_on:` (list of strings).

    Mirrors the discriminator surface of firstlanding's
    `ArchAstro.Config.Objects.SetupAction` after PR #5414.
    """
    actions = raw.get("setup_actions")
    if actions is None:
        return
    if not isinstance(actions, list):
        raise SampleError(
            f"{where}: wrapped template {template_label!r} `setup_actions:` "
            f"must be a list, got {type(actions).__name__}."
        )

    for idx, action in enumerate(actions):
        prefix = f"setup_actions[{idx}]"
        if not isinstance(action, dict):
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix} must be a mapping, got {type(action).__name__}."
            )
        action_type = action.get("action_type")
        if action_type not in SETUP_ACTION_TYPES:
            valid = ", ".join(sorted(SETUP_ACTION_TYPES))
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix}.action_type {action_type!r} is not a known type. "
                f"Valid types: {valid}."
            )

        spec = SETUP_ACTION_TYPES[action_type]
        supplied = set(action.keys()) - {"action_type"}
        missing = spec["required"] - supplied
        if missing:
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix} ({action_type}) missing required fields: "
                f"{', '.join(sorted(missing))}. Every inline setup_action "
                f"must declare `dedupe_key:` so cross-template imprints "
                f"of the same action fold into one checklist row."
            )
        unknown = supplied - spec["required"] - spec["optional"]
        if unknown:
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix} ({action_type}) has unknown fields: "
                f"{', '.join(sorted(unknown))}."
            )

        dedupe_key = action.get("dedupe_key")
        if not isinstance(dedupe_key, str) or not dedupe_key.strip():
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix}.dedupe_key must be a non-empty string."
            )

        for field in ("title", "description"):
            value = action.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SampleError(
                    f"{where}: wrapped template {template_label!r} "
                    f"{prefix}.{field} must be a non-empty string."
                )

        depends_on = action.get("depends_on")
        if depends_on is not None and (
            not isinstance(depends_on, list)
            or not all(isinstance(x, str) for x in depends_on)
        ):
            raise SampleError(
                f"{where}: wrapped template {template_label!r} "
                f"{prefix}.depends_on must be a list of strings."
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
