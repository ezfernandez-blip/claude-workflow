---
name: verify
description: How to verify changes to the claude-workflow system end-to-end (installer scripts + workflow markdown as agent config)
---

# Verifying claude-workflow changes

This repo has two runtime surfaces. Drive both when a change touches them.

## Surface 1: Python installer CLI (`scripts/`)

Install into a scratch project and inspect what lands:

```bash
SCRATCH=$(mktemp -d)
python3 scripts/init-project.py $SCRATCH/proj --name "Scratch" --description "verify"
find $SCRATCH/proj -type f | sort          # audit the installed tree
python3 scripts/sync-workflow.py $SCRATCH/proj --base-only   # update path
```

To separate regressions from pre-existing breakage, build a baseline with
`git worktree add <dir> HEAD` (when the change is uncommitted) and run the
same commands there; diff the installed trees with `diff -rq`.

**Fixed in 2.4.0 — these are now regressions if you see them again:**
- `sync-workflow.py --components templates` must work (it raised `KeyError: 'path'`; template
  entries use `source`/`destination`, not `path`)
- `init-project.py --list-variants` must work without a `project_path`
- a repeat `sync-workflow.py` on a variant project must report **zero** `(update)` lines — the base
  layer consults `baseExclusions`, so base and variant no longer take turns writing the same files
- `validate-variant.py` must exit 0 for all four bundled variants (it previously died with
  `UnicodeDecodeError` on Windows, and the variants were missing `name:` frontmatter)
- `sync-workflow.py <project>` on a **base-only** project must exit 0 — "base" means no variant
  layer, not an unresolvable variant
- no script may leave a `.claude/variants/` tree in a project, and none may delete one
- `merge-layers.py` must flatten component sources: no `.claude/{agents,commands,tasks}/<subdir>/`
- a variant's `templates/*.yaml` must never land in `.github/workflows/`

Gotchas: plain re-run of init-project.py preserves existing files; `--force`
overwrites everything including a user-filled `knowledge/team/team-roster.md`.

## Surface 2: workflow markdown (commands/tasks/agents = agent config)

The markdown's runtime is an agent following it. Spawn one subagent pointed at
the scratch project, instruct it to act ONLY per the installed `.claude/` files
(no outside knowledge, report ambiguities instead of improvising), and have it
execute concrete scenarios with checkable outputs — e.g. for team-roster:
capacity math for a known roster (2w, 6h/day, 80% capacity, 80% allocation →
48/38.4/48h), unknown-name warning text, missing-file error text. Ask it to
quote exact texts so you can diff against the task files.

To prove skills read config rather than hard-coded values: write a roster
whose calibration frontmatter is deliberately non-standard (e.g.
capacityPercent 50, workingDaysPerWeek 4, proficiency-3 multiplier 2.0),
compute the expected outputs by hand for BOTH the custom and shipped
values, and check which one the agent produces. Also strip the config
keys to exercise the documented warn-and-fallback path. Require the agent
to cite the file + frontmatter key for every number it uses.

## Structural checks (cheap, always run)

```bash
# frontmatter parses on all touched workflow files
python3 -c "import yaml; c=open('FILE').read(); yaml.safe_load(c.split('---')[1])"
# every task referenced in commands' "Tasks Invoked" exists in base/tasks/
```
