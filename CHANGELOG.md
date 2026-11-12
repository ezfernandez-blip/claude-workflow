# Changelog

All notable changes to the Claude Workflow System (base layer) are documented here.
Versioning follows release.version.minor: the third number is bumped for backward-compatible feature additions.

## [2.4.0] - 2026-08-20

Variants have two shapes, and this release makes the distinction explicit. The **repository** keeps
each variant as `variants/<name>/`, because that is the unit a pull request reviews and versions. A
**project** holds the merged flat result — `.claude/{agents,commands,tasks}` plus
`.github/workflows/` — because that is the only layout Claude Code loads from. A project never
mirrors the repository shape.

### Added

- **`.claude/workflow-manifest.json`** — the project's record of its installation: `baseVersion`,
  the variant's identity, `baseExclusions`, and every installed file tagged `"layer": "base"` or
  `"layer": "variant"`. This is what makes a handful of variant files distinguishable from the ~60
  base files beside them, and what lets `/SubmitVariant` rebuild a variant folder later.
  `init-project.py` writes it; the legacy `.claude/.workflow-version` marker is still written for
  tooling that reads it.
- **`/SubmitVariant` materializes and then removes the variant folder.** It reads the manifest,
  collects every `"layer": "variant"` file plus anything that differs from the base layer, builds a
  temporary `variants/<name>/` folder in repo shape inside a throwaway clone, generates
  `manifest.json` and `README.md`, opens the PR, and deletes the temporary folder. Nothing
  repo-shaped persists locally between submissions.
- **Basename collision detection.** Two variant files that would land on the same flat filename are
  reported instead of one silently overwriting the other based on path sort order.

### Fixed

- **Variant components are installed flat; a project never gets a variant folder.** Creating a
  custom variant could leave a `variants/<name>/`-shaped tree at `.claude/variants/<name>/` in the
  target project. Claude Code does not load components from nested folders, so those components
  were installed but inert.
- **The legacy-layout repair is now non-destructive.** `merge_legacy_variant_folder()` (shared by
  `init-project.py`, `merge-layers.py`, and `sync-workflow.py`) copies components out of a
  `.claude/variants/` tree into the flat directories with no-overwrite semantics, then **leaves the
  folder in place** and tells the user how to remove it. The previous implementation deleted the
  tree, which could destroy a half-authored variant (anything that was not a `.md` under
  `agents`/`commands`/`tasks` — templates, README, assets — was not salvaged first).
- **A variant's `templates/*.yaml` is no longer promoted into `.github/workflows/`.** Both the
  markdown and YAML passes are now scoped by parent directory, so only `github-workflows/*.yml`
  becomes a GitHub Actions workflow.
- **Nested variant sources are picked up.** The merge matches any ancestor directory, so
  `agents/sub/deep.md` reaches `.claude/agents/deep.md` — previously the repair handled only
  immediate parents, making it weaker than the install path it was meant to repair.
- **Variant files missing from a manifest are no longer dropped.** `init-project.py` and
  `sync-workflow.py` install unlisted `agents`/`commands`/`tasks` files and a variant's
  `github-workflows/`. All bundled variants have complete manifests, so this is a no-op for them.
- **A manifest-declared `workflows` entry lands in `.github/workflows/`.** `sync-workflow.py` wrote
  it to a `github-workflows/` directory at the project root, so declaring a workflow was worse than
  leaving it unlisted.
- **`sync-workflow.py` exits non-zero when variant resolution fails.** It printed the error and
  still reported `✓ Sync completed!` with exit 0. (The old code exited 1 here only by accident, via
  the encoding crash below.)
- **`--variant-path` now wins over the project's recorded variant name**, instead of being ignored
  whenever `settings.json` already named one (typically `base`).
- **Python scripts no longer crash on Windows.** Two separate defects: status glyphs (`✓`/`✗`/`→`)
  could not be encoded to a cp1252 console, and file reads used the platform default encoding.
  `validate-variant.py` could not read three of the four bundled variants at all. All six scripts
  now force UTF-8 on stdout/stderr and pass `encoding='utf-8'` on every read and write.
- **`--variant-path` expands `~`.** `Path.resolve()` does not, so a tilde path silently resolved to
  a literal `~` subdirectory of the working directory.
- **All four bundled variants now pass `validate-variant.py`.** Two defects were hidden behind the
  encoding crash above:
  - 18 component files were missing the `name:` frontmatter field the validator requires: 6 of
    `electron-desktop`'s 11 components had no frontmatter at all and 3 more were missing only
    `name:`, while the other three variants were missing it on their
    `ImplementFeature`/`FixBug`/`RefactorCode` overrides. Every `name:` matches its filename and its
    manifest entry.
  - `projectType` was validated against a closed allowlist (`nextjs, react, node, python, crewai,
    generic`) that rejected `electron` and `agentuity` — two variants this repository ships — and
    would have rejected every `swift`/`flutter`/`rust`/`go` variant `/CreateVariant` invites users
    to author. It is now validated as a lowercase slug in both `validate-variant.py` and
    `base/schema/manifest.schema.json`. Malformed values are still rejected.

  This matters more than before: `/SubmitVariant` now runs the validator on the folder it
  materializes, so a submission would have failed on either defect.

### Fixed (second QA pass, pre-release)

- **`merge-layers.py` did not flatten component sources.** It preserved the source tree, so a
  variant with `agents/sub/x.md` produced `.claude/agents/sub/x.md` — installed but inert, i.e. the
  very defect this release exists to fix, surviving in the one script that had not been updated.
  Component directories now merge by basename (with collision reporting); `templates/` keeps its
  tree, because there the relative path *is* the destination.
- **`merge-layers.py` crashed writing merged markdown.** The read side was fixed earlier in this
  release and the write side was not, so the failure merely moved from `UnicodeDecodeError` to
  `UnicodeEncodeError` — same command, same exit 1, still unusable on a cp1252 console, after
  writing about half the files.
- **`sync-workflow.py <project>` failed on a base-only project.** The new error propagation treated
  `project.variant: "base"` — what `init-project.py` writes for every base install — as an
  unresolvable variant and exited 1. `base`/empty now means "no variant layer". This is the most
  common documented invocation.
- **`sync-workflow.py`'s sweep had no collision handling**, so it picked the opposite winner from
  `init-project.py` for two sources sharing a basename (flipping file content between runs) and
  rewrote the same destination on every run. Both scripts now keep the first-sorted file and report
  the collision.
- **`init-project.py` mislabelled the user's own files.** Anything already in `.claude/` that
  neither layer installed was recorded as `layer: "base"`. Those files are now `layer: "local"`, and
  `/SubmitVariant` is required to exclude them — without this, a private file kept in `.claude/`
  could be swept into a public pull request.
- **`init-project.py` and `merge-layers.py` reported success on genuine failure.** A missing
  `--variant`, a `--variant-path` without a manifest, or a nonexistent variant directory printed a
  warning and exited 0 after installing base only. All now exit 1. `init-project.py` also no longer
  writes an uninstalled variant name into `settings.json`.
- **Malformed manifests no longer crash the validator.** A non-string `projectType` slipped through
  a `str()` coercion; an empty or non-string `name` raised `IndexError`/`TypeError`; corrupt JSON
  produced a raw traceback in all four scripts. Each is now a reported validation error.
- `apply-upgrade.py` read its manifest with the platform encoding, and
  `create-upgrade-package.py` decoded `git` output with it — the latter silently mojibaked the
  generated upgrade instructions and release commit message rather than failing.
- `base/schema/manifest.schema.json` now declares `baseExclusions`, which all four bundled variants
  carry and all three installers read.
- `/SubmitVariant` no longer shells out to `python scripts/validate-variant.py`. That command is
  installed into projects by the plugin, whose only prerequisites are `git` and `curl`; requiring an
  interpreter there would have added a dependency the install never had (and bare `python` does not
  exist on macOS 12.3+ or Debian/Ubuntu without `python-is-python3`). The checks are now performed
  by reading the materialized folder, with the script offered as an optional convenience.
- `/SubmitVariant`'s cleanup was a silent no-op: `WORKDIR` was assigned in one shell block and used
  two blocks later, so `rm -rf "$WORKDIR"` ran as `rm -rf ""` while the command reported the folder
  removed. Every block now re-derives the path and the deletion is verified.
- `docs/creating-variants.md` still documented the closed `projectType` allowlist this release
  removed from both the validator and the schema.
- `.claude/skills/verify/SKILL.md` listed defects fixed in this release under "do NOT fail a change
  for these", which would have suppressed a genuine regression.

### Fixed (long-standing defects, cleared in this release)

- **`sync-workflow.py --components templates` crashed** with `KeyError: 'path'`. Component entries
  in a variant manifest use `path`; template entries use `source`/`destination`. The entry shape is
  now normalised once, so templates sync like any other component.
- **A repeat `sync-workflow.py` on a variant project churned.** The base layer never consulted
  `baseExclusions`, so it re-installed the base version of every file the variant overrides, the
  variant layer overwrote them again, and each run reported ~10 files as updated and rewrote them.
  `sync_base_layer` now takes the exclusion set — read from the project manifest, else declared in
  the variant manifest, else derived from filename overlap — and reports those files as
  `skip (variant override)`. A repeat sync now reports **zero** updates. Exclusions only ever cause
  a file to be *skipped*; nothing is deleted.
- **`init-project.py --list-variants` required a `project_path`** it never used. The positional is
  now optional, and its absence is reported cleanly when it genuinely is needed.

Note on scope: `init-project.py` still installs the full base layer before overlaying the variant,
so a script-installed variant project keeps base files the variant supersedes (e.g. `code-writer.md`
alongside `nextjs-specialist.md`). The plugin's install path applies exclusions at install time and
does not. Making the script match would change the installed file set for every bundled variant, so
it is left as a separate decision rather than folded into this release.

### Changed

- **Variants no longer exclude base agents.** All four bundled manifests had
  `baseExclusions.agents: ["code-writer"]`, and the variant commands said "Do NOT route to
  `code-writer`" - while the variant *specialists* described `code-writer` as a collaborator for
  generic work, and `GenerateTests` plus the `context-loader` task (neither excluded) referenced it
  by name. Three layers disagreed, and on the plugin path the agent was deleted while its
  references survived.

  Resolved in favour of routing: `code-writer` is a base agent and stays installed;
  `baseExclusions.agents` is now empty for every bundled variant; and each variant's
  `ImplementFeature`/`FixBug`/`RefactorCode` states a *preference* - use the specialists for work
  in the variant's domain, fall back to `code-writer` for generic code none of them covers.
  Exclusions now apply only to same-named overlays, where the base copy would otherwise overwrite
  the variant's version. Installed agent counts are unchanged (nextjs 13, electron 12, ml 14,
  agentuity 13) and the plugin path now matches the script path.

- `/CreateVariant`, `/SubmitVariant`, `/SetupWorkflow`, the `variant-management` task, and
  `docs/creating-variants.md` all now distinguish the repository shape from the project shape, and
  state that a variant authored inside a project has no folder at all.
- `sync-workflow.py`'s variant resolution looks only in the repository's `variants/`. There is no
  local staging directory to consult — a project-authored variant has no source tree.

### Migrating an affected project

Run the plugin's `/claude-workflow:update`. It merges any `.claude/variants/` components into the
flat directories, writes a manifest, and reports what it found. It does not delete the folder;
remove it yourself once you have confirmed the merge.

## [2.3.5] - 2026-07-10

### Fixed

- `apply-upgrade.py --force` now re-applies over a copy that is already at the target version, so a copy that fails `--verify` (corrupted or partially-edited files) can be repaired by re-running the upgrade. The "already upgraded" message points to both options.

## [2.3.4] - 2026-07-10

### Added

- Upgrade verification: package manifests now carry SHA-256 checksums for every file, `apply-upgrade.py` gains a `--verify` mode (confirms version, file checksums, and deletions without changing anything), and every apply run verifies itself before reporting success. `UPGRADE-INSTRUCTIONS.md` Step 4 and the manual-upgrade section use it.

## [2.3.3] - 2026-07-09

### Added

- `UPGRADE-INSTRUCTIONS.md` in upgrade packages gains a "Manual upgrade" section: copying `files/` by hand, applying deletions from the manifest, and committing with the manifest's message — for recipients who cannot run the Python applier.

## [2.3.2] - 2026-07-09

### Added

- Upgrade packages now include a generated `UPGRADE-INSTRUCTIONS.md`: step-by-step apply guide (version check, dry-run preview, apply, verify, propagate to projects), a troubleshooting table, and the CHANGELOG excerpt covering exactly the versions the recipient is receiving.

## [2.3.1] - 2026-07-09

### Added

- **Zip Upgrade Packages** — `scripts/create-upgrade-package.py` builds a self-applying upgrade zip from git history for recipients who received the repository as a zip file: it collects every file changed between two versions plus a manifest carrying the version bump and release commit message. The bundled `apply-upgrade.py` verifies the recipient's current version against the package baseline (refusing on mismatch unless `--force`), copies updates, applies deletions/renames, updates `base/VERSION`, and commits with the release message when the copy is a git repository (`--push`, `--no-commit`, `--dry-run` supported). Non-git copies get the file updates with a note to commit externally.

## [2.3.0] - 2026-07-09

### Added

- **Team Roster Configuration** — Planning is now driven by a persistent team roster at `knowledge/team/team-roster.md` in each target project instead of ad-hoc `team=` strings. The roster defines each member's name, role, seniority, velocity multiplier, allocation, and per-area skill proficiency (1-5), plus a prose role description used as estimation context.
  - New task `team-roster` (`base/tasks/team-roster.md`) with `load`, `resolve`, and `deriveComposition` operations and the authoritative Estimation Math: item sizes are calibrated to a 1.0 mid-level baseline, then adjusted per assignee by `velocityFactor` and out-of-area proficiency multipliers.
  - New template `base/templates/knowledge/team/team-roster.md.template`, markdown-native (no JSON schema), pre-populated with three example members, plus a Team Roster Guide (`README.md` installed beside the roster at `knowledge/team/README.md`) documenting every field, the estimation math, and update recipes. All calibration values live in the roster frontmatter rather than in command/task files: capacity defaults (`hoursPerDay`, `capacityPercent`, `workingDaysPerWeek`), role abbreviations, `setupDefaults` (seniority-based starting velocities and skills used by `/SetupWorkflow`), `estimation.proficiencyMultipliers` (out-of-area adjustments), and a Change Log section for tracking team changes.
  - `/SetupWorkflow` gains step 6.5 "Configure Team Roster": copies the template and offers interactive fill-in with conservative seniority-based starting values (junior 1.5, mid 1.0, senior 0.8, staff 0.7). Update mode offers to add `knowledge/team/` to existing projects.
  - `/Breakdown` gains a `suggestAssignees` argument that picks a best-fit assignee per Work Item from the roster skills matrix and shows adjusted estimates.
  - `project-metadata` gains a `verifyTeamRoster` operation; roster status is included in `verify` output alongside Linear/Coda/GitHub.

### Changed

- `/CyclePlan` and `/PRDFeasibility`: the `team` argument is now optional. When omitted, the team is loaded or derived from the roster; when provided, names are resolved against the roster (unknown names are planned at documented baseline with an explicit warning — the model never invents roles). `capacity` defaults to the roster's `defaults.capacityPercent`.
- `/PRDSequence` maps resource contention using actual role supply from the roster (weighted by allocation) instead of assuming interchangeable engineers.
- `cycle-planning` and `technical-feasibility` tasks and the `cycle-planner` agent read capacity defaults and member data from the roster; capacity numbers are no longer hardcoded (6h/day and 80% remain the shipped template defaults).
- Planning outputs state applied multipliers (e.g. `6-9h (4-6h baseline x 1.5 velocity)`) so plans are auditable.

All changes are backward compatible: every command keeps accepting its existing `team` argument.

## [2.2.5] - 2026-06-29

### Changed

- Cache project context in `session-state.json`.

## [2.2.4] - 2026-06-29

### Changed

- Session commands and the CLAUDE.md template honor the `session-state.json` cross-session handoff.

## [2.2.3] - 2026-06-29

### Removed

- JSON-schema dependency from the planning workflow; planning state is documented inline in tasks.

## [2.2.2] - 2026-06-29

### Fixed

- Variant install: flatten layout, install schema, support custom variant paths.

## [2.2.1] - 2026-03-30

### Added

- Linear Issue Description Standard (`## Overview`, `## Deliverables`, `## Definition of Done`) enforced in `/LogNewFeature`, `/Breakdown`, and `mcp-sync.createIssue`.
- `/EndSession` posts a project update document to Linear when issues are completed during a session.
- `/LogNewFeature` generates full descriptions with acceptance criteria.

## [2.2.0] - 2026-02-27

### Added

- `baseExclusions` and variant-specific commands/tasks.

## [2.0.0] - 2026-02-04

### Added

- PRD-to-Cycle planning workflow (PRD intake, validation, enrichment, feasibility, sequencing, breakdown, cycle management).
