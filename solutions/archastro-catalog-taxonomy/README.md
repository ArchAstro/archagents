# ArchAstro Catalog Taxonomy

The shared catalog vocabulary for the ArchAstro Solution catalog: every
`SolutionCategory` and `SolutionTag` the published samples reference
through their `category_keys` / `tag_keys`. Installing this bundle seeds
those definitions so the catalog renders real category and tag labels
instead of bare keys.

This is a **hidden, config-only Solution** — it ships no deployable
template (no agent, tool, or script). It exists only to import its child
`SolutionCategory` / `SolutionTag` rows, so it never appears in the
catalog list/show APIs itself.

## Install

```sh
archagent install agentsample archastro-catalog-taxonomy
```

`upload_configs` uploads every YAML under `taxonomy/` as a top-level
config (keyed by `kind:`), then `deploy_solution` deploys the hidden
Solution that adopts those rows as its children.

## Bundle layout

- `solution.yaml` — the hidden config-only Solution (catalog metadata)
- `taxonomy/*.yaml` — one `SolutionCategory` or `SolutionTag` per file
- `sample.yaml` — install steps (`upload_configs` + `deploy_solution`)

## Editing the taxonomy

Add or change a category/tag by editing the matching file under
`taxonomy/` (or adding a new `*-category.yaml` / `*-tag.yaml`). Every
`key` is referenced by other Solutions, so renaming a `key` is a
breaking change — update the referencing Solutions' `category_keys` /
`tag_keys` in the same pass.
