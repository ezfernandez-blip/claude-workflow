#!/usr/bin/env python3
"""Create a zip upgrade package for zip-delivered claude-workflow copies.

Collects every file that changed between two versions of this repository
(using git), bundles them with apply-upgrade.py and a manifest carrying the
version bump and release commit message. The recipient unzips the package
and runs apply-upgrade.py against their copy.

    python scripts/create-upgrade-package.py --from <ref> [--to <ref>]

Example — package everything since the v2.2.5 release commit:

    python scripts/create-upgrade-package.py --from 6ed89e9
    # -> dist/claude-workflow-upgrade-2.2.5-to-2.3.0.zip
"""

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

# Windows consoles default to a legacy code page (cp1252) that cannot encode the status
# glyphs used below, which made every run end in UnicodeEncodeError. Force UTF-8 output.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).resolve().parent.parent


def git(*cmd: str) -> str:
    # text=True decodes with the locale encoding, which silently mojibakes the CHANGELOG
    # excerpt and commit message on a cp1252 console. Pin it.
    result = subprocess.run(['git'] + list(cmd), cwd=REPO_ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"✗ git {' '.join(cmd)} failed:\n{result.stderr.strip()}")
        sys.exit(1)
    return result.stdout


def git_bytes(*cmd: str) -> bytes:
    result = subprocess.run(['git'] + list(cmd), cwd=REPO_ROOT,
                            capture_output=True)
    if result.returncode != 0:
        print(f"✗ git {' '.join(cmd)} failed:\n{result.stderr.decode().strip()}")
        sys.exit(1)
    return result.stdout


def version_at(ref: str) -> str:
    return git('show', f'{ref}:base/VERSION').strip()


def changed_files(from_ref: str, to_ref: str, excludes: list) -> tuple:
    """Return (files_to_copy, deletions) between two refs."""
    copies, deletions = [], []
    for line in git('diff', '--name-status', from_ref, to_ref).splitlines():
        parts = line.split('\t')
        status = parts[0]
        if status.startswith('R'):          # rename: delete old, copy new
            old, new = parts[1], parts[2]
            deletions.append(old)
            copies.append(new)
        elif status.startswith('C'):        # copy: new path only
            copies.append(parts[2])
        elif status == 'D':
            deletions.append(parts[1])
        else:                               # A, M, T
            copies.append(parts[1])
    def keep(path):
        return not any(path.startswith(e) for e in excludes)
    return [p for p in copies if keep(p)], [p for p in deletions if keep(p)]


def build_commit_message(from_ref: str, to_ref: str,
                         from_v: str, to_v: str) -> str:
    subjects = git('log', '--format=%s', f'{from_ref}..{to_ref}').splitlines()
    lines = [f"chore: upgrade Claude Workflow System {from_v} -> {to_v}", "",
             "Applied from upgrade package. Includes:"]
    lines += [f"- {s}" for s in reversed(subjects)]
    return '\n'.join(lines)


def changelog_excerpt(to_ref: str, from_v: str) -> str:
    """Everything in CHANGELOG.md (at to_ref) newer than from_v."""
    probe = subprocess.run(['git', 'cat-file', '-e', f'{to_ref}:CHANGELOG.md'],
                           cwd=REPO_ROOT, capture_output=True)
    if probe.returncode != 0:
        return "(No CHANGELOG.md in this version.)"
    text = git('show', f'{to_ref}:CHANGELOG.md')
    start = text.find('\n## [')
    if start == -1:
        return "(No entries found in CHANGELOG.md.)"
    end = text.find(f'## [{from_v}]')
    return text[start:end if end != -1 else None].strip()


def manual_checklist(from_v: str, to_v: str, added: list) -> str:
    if added:
        shown = added[:12]
        new_files_block = '\n'.join(f"   - `{p}`" for p in shown)
        if len(added) > len(shown):
            new_files_block += (f"\n   - ...and {len(added) - len(shown)} "
                                f"more (see `files` in `manifest.json`)")
    else:
        new_files_block = ("   (This upgrade only updates existing files — "
                           "spot-check a few against `files/` instead.)")

    try:
        crosses_2_3_0 = tuple(map(int, from_v.split('.'))) < (2, 3, 0)
    except ValueError:
        crosses_2_3_0 = False

    if crosses_2_3_0:
        project_checks = """**Check 4** — In each project, run `/claude-workflow:update` (plugin) or
`/SetupWorkflow` (update mode). New in the 2.3.x series: it offers a
"Configure Team Roster" step — older versions never mention a roster. Take
the interactive fill-in and add your real team members.

**Check 5** — Afterwards, confirm these exist in the project:
   - `.claude/tasks/team-roster.md`
   - `knowledge/team/team-roster.md` (your team configuration)
   - `knowledge/team/README.md` (explains every field — worth a read)

**Run the functional test**

**Check 6** — In Claude Code, inside the project, run — with NO team argument:

    /CyclePlan duration="1w" goal="upgrade smoke test"

- New version, roster filled in: a capacity table computed from
  `knowledge/team/team-roster.md`, showing per-member adjustments.
- New version, roster missing: a "No team roster found..." message
  pointing you to `/SetupWorkflow`.
- OLD version: it insists on a `team=` argument — the project was not
  updated; redo Check 4."""
    else:
        project_checks = """**Check 4** — In each project, run `/claude-workflow:update` (plugin) or
`/SetupWorkflow` (update mode) to sync the updated components.

**Check 5** — Spot-check that a file this upgrade changed (see `files` in
`manifest.json`) now matches its copy under this package's `files/` folder
in your project's `.claude/` directory."""

    return f"""## Manual verification checklist (no tools needed)

Prefer checking by hand? Here is what you should be able to SEE after the
upgrade — Checks 1-3 in your repo copy, the rest in each project that uses it.

**Check your claude-workflow repo copy**

**Check 1** — Open `base/VERSION`: it should read `{to_v}` (`{from_v}` means
the upgrade did not apply).

**Check 2** — Confirm these new files exist:
{new_files_block}

**Check 3** (git repos only) — Run `git log -1`: you should see a commit
starting with "chore: upgrade Claude Workflow System".

**Update and check each project**

Upgrading the repo copy does NOT update your projects automatically.

{project_checks}
"""


def build_instructions(from_v: str, to_v: str, copies: list,
                       deletions: list, to_ref: str, added: list) -> str:
    deletion_note = (
        f"and removes {len(deletions)} obsolete file(s)" if deletions
        else "and removes nothing"
    )
    return f"""# Upgrading Claude Workflow System {from_v} -> {to_v}

This package updates an existing copy of the claude-workflow repository
from version {from_v} to {to_v}. It contains everything needed; no
internet access or extra downloads are required.

## Before you start

- You need Python 3.8 or later (`python --version` or `python3 --version`).
- Locate your claude-workflow copy: the folder that contains `base/VERSION`.
- If your copy is a git repository, commit or stash any local changes
  first so the upgrade lands as its own clean commit.
- If your copy is NOT a git repository, make a backup copy of the folder
  before applying — there is no undo without one.

## Step 1 — Check your current version

    cat /path/to/your/claude-workflow/base/VERSION

It should read `{from_v}`. If it shows a different version, stop and
request the matching upgrade package (or see Troubleshooting below).

## Step 2 — Preview the changes (recommended)

From this package folder (where this file lives):

    python apply-upgrade.py /path/to/your/claude-workflow --dry-run

This lists every file that would be created, updated, or deleted,
without touching anything. This upgrade copies {len(copies)} file(s)
{deletion_note}; the full list is in `manifest.json`.

## Step 3 — Apply the upgrade

    python apply-upgrade.py /path/to/your/claude-workflow

What happens:
1. Your copy's version is checked against this package's baseline
   ({from_v}); on mismatch nothing is changed.
2. Updated files are copied into place and obsolete files removed.
3. `base/VERSION` becomes {to_v}.
4. If the copy is a git repository, a commit is created with the
   release notes as its message. (Use `--no-commit` to skip this,
   or `--push` to also push the branch to origin.)

## Step 4 — Verify

    python apply-upgrade.py /path/to/your/claude-workflow --verify

This changes nothing; it confirms the version is {to_v} and checks every
upgraded file against the package checksums, so you know the upgrade is
complete and intact. Expect:

    ✓ Verified: this copy matches upgrade package {to_v} exactly ({len(copies)} file(s) checked).

For git copies, `git -C /path/to/your/claude-workflow log -1` should also
show the upgrade commit.

## Step 5 — Propagate to your projects (optional)

Upgrading this repository copy does not change projects that were set up
from it. To bring an existing project up to date, run `/SetupWorkflow`
in that project (update mode), or use
`python scripts/sync-workflow.py /path/to/project` for the script route.

{manual_checklist(from_v, to_v, added)}
## Manual upgrade (no Python, or the script won't run)

Everything the script does can be done by hand:

1. Copy the entire contents of this package's `files/` folder into the
   root of your claude-workflow copy, keeping the folder structure and
   overwriting existing files ({len(copies)} file(s); full list under
   `files` in `manifest.json`).
2. Delete any files listed under `deletions` in `manifest.json`
   {'(' + ', '.join(deletions) + ')' if deletions else '(none for this upgrade)'}.
3. Confirm `base/VERSION` now reads `{to_v}`.
4. If your copy is a git repository, commit everything using the message
   found under `commitMessage` in `manifest.json`, and push.
5. If Python is available anywhere, confirm your manual work with
   `python apply-upgrade.py /path/to/your/claude-workflow --verify`;
   otherwise spot-check a few copied files against `files/` and compare
   sizes. The checksums in `manifest.json` are SHA-256 if you prefer
   `sha256sum` / `certutil -hashfile`.

## Troubleshooting

| Symptom | Meaning / fix |
|---------|---------------|
| "Target is at X but this package upgrades from {from_v}" | Your copy is a different version. Request the package matching your version, or run with `--force` to overwrite wholesale (only safe if you have no local modifications). |
| "Target is already at {to_v}. Nothing to do." | The upgrade was already applied. Nothing happened; this is safe. |
| "base/VERSION not found" | The path you gave is not a claude-workflow copy. Point at the folder that contains `base/`, `docs/`, `scripts/`. |
| "git commit failed" | Files are applied and staged; commit manually with any message (the intended message is `commitMessage` in `manifest.json`). |
| Need to undo (git copy) | `git reset --hard HEAD~1` if you committed, or `git checkout -- .` if not. |
| Need to undo (non-git copy) | Restore the backup you made before Step 3. |

## What's new in this upgrade

{changelog_excerpt(to_ref, from_v)}
"""


def main():
    parser = argparse.ArgumentParser(
        description='Create a zip upgrade package from git history'
    )
    parser.add_argument('--from', dest='from_ref', required=True,
                        help='Git ref of the version the recipient has '
                             '(commit, tag, or branch)')
    parser.add_argument('--to', dest='to_ref', default='HEAD',
                        help='Git ref to upgrade to (default: HEAD)')
    parser.add_argument('--output', '-o', type=Path,
                        default=REPO_ROOT / 'dist',
                        help='Output directory for the zip (default: dist/)')
    parser.add_argument('--exclude', action='append', default=[],
                        help='Path prefix to leave out of the package '
                             '(repeatable, e.g. --exclude docs/)')
    args = parser.parse_args()

    from_v = version_at(args.from_ref)
    to_v = version_at(args.to_ref)
    if from_v == to_v:
        print(f"✗ base/VERSION is {from_v} at both refs — nothing to package.")
        sys.exit(1)

    copies, deletions = changed_files(args.from_ref, args.to_ref, args.exclude)
    if not copies and not deletions:
        print("✗ No changed files between the given refs.")
        sys.exit(1)
    if 'base/VERSION' not in copies:
        print("✗ base/VERSION did not change between refs; refusing to build "
              "an upgrade that cannot verify itself.")
        sys.exit(1)

    name = f"claude-workflow-upgrade-{from_v}-to-{to_v}"
    print(f"Package: {name}")
    print(f"  {len(copies)} file(s) to copy, {len(deletions)} deletion(s)")

    payload = {rel: git_bytes('show', f'{args.to_ref}:{rel}')
               for rel in sorted(copies)}

    # files that did not exist at the old version (for the manual checklist)
    added = [rel for rel in sorted(copies)
             if subprocess.run(
                 ['git', 'cat-file', '-e', f'{args.from_ref}:{rel}'],
                 cwd=REPO_ROOT, capture_output=True).returncode != 0]

    manifest = {
        'package': name,
        'fromVersion': from_v,
        'toVersion': to_v,
        'fromRef': git('rev-parse', args.from_ref).strip(),
        'toRef': git('rev-parse', args.to_ref).strip(),
        'created': date.today().isoformat(),
        'commitMessage': build_commit_message(args.from_ref, args.to_ref,
                                              from_v, to_v),
        'files': sorted(copies),
        'deletions': sorted(deletions),
        'checksums': {rel: hashlib.sha256(data).hexdigest()
                      for rel, data in payload.items()},
    }

    # apply-upgrade.py from the target ref, so package and applier match;
    # fall back to the working tree while the applier is not yet committed.
    probe = subprocess.run(
        ['git', 'cat-file', '-e', f'{args.to_ref}:scripts/apply-upgrade.py'],
        cwd=REPO_ROOT, capture_output=True)
    if probe.returncode == 0:
        apply_script = git_bytes('show', f'{args.to_ref}:scripts/apply-upgrade.py')
    else:
        apply_script = (REPO_ROOT / 'scripts' / 'apply-upgrade.py').read_bytes()
        print("  ! apply-upgrade.py taken from working tree "
              "(not committed at --to ref yet)")

    args.output.mkdir(parents=True, exist_ok=True)
    zip_path = args.output / f"{name}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{name}/apply-upgrade.py", apply_script)
        zf.writestr(f"{name}/manifest.json", json.dumps(manifest, indent=2))
        zf.writestr(f"{name}/UPGRADE-INSTRUCTIONS.md",
                    build_instructions(from_v, to_v, copies, deletions,
                                       args.to_ref, added))
        for rel, data in payload.items():
            zf.writestr(f"{name}/files/{rel}", data)

    print(f"✓ Wrote {zip_path}")
    print("\nDeliver the zip. It contains UPGRADE-INSTRUCTIONS.md with the")
    print("full step-by-step guide; the short version for the recipient:")
    print(f"  unzip {zip_path.name} && cd {name}")
    print("  python apply-upgrade.py /path/to/their/claude-workflow")


if __name__ == '__main__':
    main()
