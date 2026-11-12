#!/usr/bin/env python3
"""Apply a Claude Workflow System upgrade package to an existing copy.

This script ships inside an upgrade zip created by create-upgrade-package.py.
Run it from the unzipped package directory, pointing at your claude-workflow
copy:

    python apply-upgrade.py /path/to/claude-workflow

It copies the updated files into place, removes files deleted in the new
version, updates base/VERSION, and — when the target is a git repository —
commits the change with the release message from the manifest.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Windows consoles default to a legacy code page (cp1252) that cannot encode the status
# glyphs used below, which made every run end in UnicodeEncodeError. Force UTF-8 output.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PACKAGE_DIR = Path(__file__).resolve().parent


def load_manifest() -> dict:
    manifest_path = PACKAGE_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f"✗ manifest.json not found next to this script ({PACKAGE_DIR})")
        print("  Run this script from inside the unzipped upgrade package.")
        sys.exit(1)
    with open(manifest_path, encoding='utf-8') as f:
        return json.load(f)


def read_version(target: Path) -> str:
    version_file = target / 'base' / 'VERSION'
    if not version_file.exists():
        print(f"✗ {version_file} not found — is this a claude-workflow copy?")
        sys.exit(1)
    return version_file.read_text(encoding='utf-8').strip()


def verify_target(target: Path, manifest: dict, files_dir: Path) -> list:
    """Return a list of problems; empty means the copy matches the package."""
    problems = []
    current = read_version(target)
    if current != manifest['toVersion']:
        problems.append(f"base/VERSION is {current}, expected "
                        f"{manifest['toVersion']}")
    checksums = manifest.get('checksums', {})
    for rel in manifest['files']:
        dst = target / rel
        if not dst.exists():
            problems.append(f"missing: {rel}")
            continue
        actual = hashlib.sha256(dst.read_bytes()).hexdigest()
        if rel in checksums:
            expected = checksums[rel]
        elif (files_dir / rel).exists():   # older package without checksums
            expected = hashlib.sha256((files_dir / rel).read_bytes()).hexdigest()
        else:
            continue
        if actual != expected:
            problems.append(f"content differs: {rel}")
    for rel in manifest.get('deletions', []):
        if (target / rel).exists():
            problems.append(f"should have been deleted: {rel}")
    return problems


def is_git_repo(target: Path) -> bool:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=target, capture_output=True, text=True
        )
        return result.returncode == 0 and result.stdout.strip() == 'true'
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Apply a Claude Workflow System upgrade package'
    )
    parser.add_argument(
        'target', type=Path, nargs='?', default=Path('.'),
        help='Path to the claude-workflow copy to upgrade (default: current directory)'
    )
    parser.add_argument(
        '--dry-run', '-n', action='store_true',
        help='Show what would change without touching any file'
    )
    parser.add_argument(
        '--verify', action='store_true',
        help='Check an already-upgraded copy against this package '
             '(version, file checksums, deletions); changes nothing'
    )
    parser.add_argument(
        '--force', '-f', action='store_true',
        help='Apply even if the installed version does not match the package baseline'
    )
    parser.add_argument(
        '--no-commit', action='store_true',
        help='Copy files but do not create a git commit'
    )
    parser.add_argument(
        '--push', action='store_true',
        help='After committing, push the current branch to origin'
    )
    args = parser.parse_args()

    manifest = load_manifest()
    target = args.target.resolve()
    files_dir = PACKAGE_DIR / 'files'

    current = read_version(target)
    from_v, to_v = manifest['fromVersion'], manifest['toVersion']

    print(f"Upgrade package: {from_v} -> {to_v}")
    print(f"Target: {target} (currently {current})")
    print()

    if args.verify:
        problems = verify_target(target, manifest, files_dir)
        if problems:
            print(f"✗ Verification failed ({len(problems)} problem(s)):")
            for p in problems:
                print(f"  - {p}")
            print("\nRe-run the upgrade (or fix the listed files manually).")
            sys.exit(1)
        print(f"✓ Verified: this copy matches upgrade package {to_v} exactly "
              f"({len(manifest['files'])} file(s) checked).")
        sys.exit(0)

    if current == to_v and not args.force:
        print(f"✓ Target is already at {to_v}. Nothing to do.")
        print("  Use --verify to check integrity, or --force to re-apply.")
        sys.exit(0)
    if current != from_v and not args.force:
        print(f"✗ Target is at {current} but this package upgrades from {from_v}.")
        print("  Use --force to apply anyway (files are overwritten wholesale).")
        sys.exit(1)

    copies = manifest['files']
    deletions = manifest.get('deletions', [])

    for rel in copies:
        src = files_dir / rel
        dst = target / rel
        if not src.exists():
            print(f"✗ Package is incomplete: missing files/{rel}")
            sys.exit(1)
        action = 'update' if dst.exists() else 'create'
        print(f"  {action}: {rel}")
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for rel in deletions:
        dst = target / rel
        if dst.exists():
            print(f"  delete: {rel}")
            if not args.dry_run:
                dst.unlink()
        else:
            print(f"  ! delete skipped (not present): {rel}")

    if args.dry_run:
        print(f"\nDry run: no files changed. {len(copies)} to copy, "
              f"{len(deletions)} to delete.")
        sys.exit(0)

    problems = verify_target(target, manifest, files_dir)
    if problems:
        print(f"\n✗ Post-apply verification failed ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"\n✓ Files applied and verified. Version is now {to_v}.")

    if not is_git_repo(target):
        print("! Target is not a git repository — skipping commit.")
        print("  If you track this copy elsewhere, commit the changes there.")
        sys.exit(0)
    if args.no_commit:
        print("! --no-commit: changes are staged in the working tree only.")
        sys.exit(0)

    paths = copies + deletions
    subprocess.run(['git', 'add', '--'] + paths, cwd=target, check=True)
    result = subprocess.run(
        ['git', 'commit', '-m', manifest['commitMessage']],
        cwd=target, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("! git commit failed — files are applied and staged, commit manually:")
        print(result.stderr.strip())
        sys.exit(1)
    print(f"✓ Committed: {result.stdout.strip().splitlines()[0]}")

    if args.push:
        result = subprocess.run(['git', 'push'], cwd=target,
                                capture_output=True, text=True)
        if result.returncode != 0:
            print("! git push failed — push manually:")
            print(result.stderr.strip())
            sys.exit(1)
        print("✓ Pushed.")


if __name__ == '__main__':
    main()
