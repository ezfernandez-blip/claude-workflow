#!/usr/bin/env python3
"""
Claude Workflow System - Sync Tool

Synchronizes workflow components between the workflow repository and a target project.
Supports selective sync of components and handles merge strategies.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Windows consoles default to a legacy code page (cp1252) that cannot encode the status
# glyphs used below, which made every run end in UnicodeEncodeError. Force UTF-8 output.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent


def load_json(path: Path) -> Dict:
    """Load and parse a JSON file, reporting malformed JSON instead of raising a traceback."""
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: {path} is not valid JSON: {exc}")
            sys.exit(1)


def save_json(path: Path, data: Dict) -> None:
    """Save data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_file_hash(path: Path) -> str:
    """Get a simple hash of file contents for comparison."""
    import hashlib
    if not path.exists():
        return ""
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def files_differ(src: Path, dst: Path) -> bool:
    """Check if two files have different contents."""
    return get_file_hash(src) != get_file_hash(dst)


def sync_directory(
    src: Path,
    dst: Path,
    strategy: str = 'overlay',
    dry_run: bool = False,
    exclude_names: Optional[set] = None
) -> List[Tuple[str, str]]:
    """
    Sync a directory with specified strategy.

    Strategies:
    - overlay: Copy new files, update existing (src wins)
    - replace: Delete dst contents, copy all from src
    - merge: Only copy files that don't exist in dst

    Returns list of (action, path) tuples.
    """
    actions = []

    if not src.exists():
        return [(f"skip (not found)", str(src))]

    if strategy == 'replace':
        if dst.exists() and not dry_run:
            shutil.rmtree(dst)
        actions.append(('replace', str(dst)))

    if not dst.exists() and not dry_run:
        dst.mkdir(parents=True, exist_ok=True)

    for item in src.rglob('*'):
        if item.is_dir():
            continue

        if exclude_names and item.name in exclude_names:
            actions.append(('skip (variant override)', item.name))
            continue

        relative_path = item.relative_to(src)
        dst_item = dst / relative_path

        if dst_item.exists():
            if strategy == 'merge':
                actions.append(('skip (exists)', str(relative_path)))
                continue
            elif files_differ(item, dst_item):
                actions.append(('update', str(relative_path)))
                if not dry_run:
                    dst_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst_item)
            else:
                actions.append(('unchanged', str(relative_path)))
        else:
            actions.append(('create', str(relative_path)))
            if not dry_run:
                dst_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_item)

    return actions


def detect_project_variant(project_path: Path) -> Optional[str]:
    """Detect the variant used by a project."""
    settings_path = project_path / '.claude' / 'settings.json'
    if settings_path.exists():
        try:
            settings = load_json(settings_path)
            return settings.get('project', {}).get('variant')
        except:
            pass
    return None


def get_base_version() -> str:
    """Get the current base layer version."""
    version_file = REPO_ROOT / 'base' / 'VERSION'
    if version_file.exists():
        return version_file.read_text(encoding='utf-8').strip()
    return "0.0.0"


def resolve_base_exclusions(project_path: Path, variant_dir: Optional[Path]) -> Dict[str, List[str]]:
    """Base component stems the active variant replaces, and which base must not re-add.

    Read from the project manifest first (written by init-project.py / the plugin), then from
    the variant manifest. Without this, sync_base_layer re-installs a base file that the variant
    overrode, the variant layer overwrites it again, and every run reports the same files as
    updated - ~10 redundant writes per run on a variant project.
    """
    empty = {'agents': [], 'commands': [], 'tasks': []}

    manifest_path = project_path / '.claude' / 'workflow-manifest.json'
    if manifest_path.exists():
        recorded = load_json(manifest_path).get('baseExclusions')
        if recorded:
            return {k: list(recorded.get(k, [])) for k in empty}

    if variant_dir is not None:
        vm = variant_dir / 'manifest.json'
        if vm.exists():
            declared = load_json(vm).get('baseExclusions')
            if declared:
                return {k: list(declared.get(k, [])) for k in empty}

            # No explicit declaration: a variant component that shares a base filename is an
            # override, so the base version must be skipped.
            components = load_json(vm).get('components', {})
            derived = dict(empty)
            for comp in derived:
                names = set()
                for entry in components.get(comp, []) or []:
                    rel = entry.get('path') or entry.get('source')
                    if rel:
                        names.add(Path(rel).stem)
                src_dir = variant_dir / comp
                if src_dir.exists():
                    names.update(f.stem for f in src_dir.rglob('*.md'))
                base_stems = {f.stem for f in (REPO_ROOT / 'base' / comp).glob('*.md')}
                derived[comp] = sorted(names & base_stems)
            return derived

    return dict(empty)


def sync_base_layer(
    project_path: Path,
    components: List[str],
    strategy: str = 'overlay',
    dry_run: bool = False,
    exclusions: Optional[Dict[str, List[str]]] = None
) -> Dict[str, List[Tuple[str, str]]]:
    """Sync base layer components to project, skipping any the active variant replaces."""
    results = {}
    base_dir = REPO_ROOT / 'base'
    exclusions = exclusions or {}

    component_mapping = {
        'commands': ('.claude/commands', 'commands'),
        'agents': ('.claude/agents', 'agents'),
        'tasks': ('.claude/tasks', 'tasks'),
        'workflows': ('.github/workflows', 'github-workflows'),
    }

    for component in components:
        if component not in component_mapping:
            results[component] = [('error', f'Unknown component: {component}')]
            continue

        dst_rel, src_rel = component_mapping[component]
        src = base_dir / src_rel
        dst = project_path / dst_rel

        excluded = {f'{stem}.md' for stem in exclusions.get(component, [])}
        actions = sync_directory(src, dst, strategy, dry_run, exclude_names=excluded)
        results[component] = actions

    return results


def merge_legacy_variant_folder(project_path: Path, dry_run: bool = False) -> None:
    """Merge a legacy `.claude/variants/` tree into the flat layout. Never deletes anything.

    The repository stores each variant as `variants/<name>/` because that is the unit a pull
    request reviews. A *project* holds the merged flat result instead - `.claude/{agents,commands,
    tasks}` plus `.github/workflows/` - because Claude Code does not load components from nested
    folders. Installs made before 2.4.0 could leave the repo-shaped tree inside the project, where
    its components are present but inert.

    This merges those components into the flat directories so they become active. It is
    deliberately non-destructive:

    - Existing flat files are never overwritten, so a stale nested copy cannot clobber a newer one.
    - The `.claude/variants/` folder is left in place. It is the user's content, quite possibly
      untracked in git, and removing it is the user's decision - not an installer's.
    """
    stray = project_path / '.claude' / 'variants'
    if not stray.exists():
        return

    print(f"  Legacy variant folder found: {stray}")
    merged, skipped = 0, 0

    def _place(src: Path, dst_dir: Path, label: str) -> None:
        nonlocal merged, skipped
        dst = dst_dir / src.name
        if dst.exists():
            print(f"    skipped {src.name} (already present in {label})")
            skipped += 1
            return
        if dry_run:
            print(f"    would merge {src.name} -> {label}")
            merged += 1
            return
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"    merged {src.name} -> {label}")
        merged += 1

    # Components: match on any ancestor directory, so nested sources are picked up too.
    for comp in ('agents', 'commands', 'tasks'):
        dst_dir = project_path / '.claude' / comp
        for src in sorted(stray.rglob('*.md')):
            if comp not in src.relative_to(stray).parts[:-1]:
                continue
            _place(src, dst_dir, f".claude/{comp}/")

    # Workflows: scoped to github-workflows/, so a variant's templates/*.yaml is not promoted
    # into .github/workflows/ where GitHub would try to run it.
    workflows_dst = project_path / '.github' / 'workflows'
    for src in sorted(list(stray.rglob('*.yml')) + list(stray.rglob('*.yaml'))):
        if 'github-workflows' not in src.relative_to(stray).parts[:-1]:
            continue
        _place(src, workflows_dst, '.github/workflows/')

    print(f"  Merged {merged} component(s), skipped {skipped} already present.")
    print(f"  Left {stray} in place - review it, then remove it yourself when satisfied:")
    print(f"    rm -rf {stray}")


def resolve_variant_dir(variant_name: str) -> Optional[Path]:
    """Locate a variant's source directory in this repository.

    Repository variants live in `variants/<name>/`. A variant authored inside a project has no
    folder at all - its components live in the project's flat `.claude/` directories and are
    tracked in `.claude/workflow-manifest.json` - so there is nothing to resolve for those.
    """
    candidate = REPO_ROOT / 'variants' / variant_name
    return candidate if (candidate / 'manifest.json').exists() else None


def sync_variant_layer(
    project_path: Path,
    variant_name: str,
    components: List[str],
    strategy: str = 'overlay',
    dry_run: bool = False,
    variant_dir: Optional[Path] = None
) -> Dict[str, List[Tuple[str, str]]]:
    """Sync variant layer components to project (flattened into .claude/*)."""
    results = {}
    if variant_dir is None:
        variant_dir = resolve_variant_dir(variant_name)
    if variant_dir is None:
        return {'error': [('error', f'Variant source not found: {variant_name}')]}

    manifest_path = variant_dir / 'manifest.json'
    if not manifest_path.exists():
        return {'error': [('error', f'Variant manifest not found: {variant_name}')]}

    manifest = load_json(manifest_path)
    manifest_components = manifest.get('components', {})

    flat_dirs = {
        'agents': project_path / '.claude' / 'agents',
        'commands': project_path / '.claude' / 'commands',
        'tasks': project_path / '.claude' / 'tasks',
        'workflows': project_path / '.github' / 'workflows',
    }

    for component in components:
        actions = []
        for item in manifest_components.get(component, []):
            # Component entries use `path`; template entries use `source`/`destination`.
            # Reading item['path'] unconditionally is what made --components templates crash.
            rel_source = item.get('path') or item.get('source')
            if not rel_source:
                actions.append(('skip (no path/source)', str(item.get('name', item))))
                continue

            src = variant_dir / rel_source
            label = rel_source

            if component in flat_dirs:
                dst = flat_dirs[component] / Path(rel_source).name
            elif component == 'templates':
                destination = item.get('destination')
                if not destination:
                    actions.append(('skip (no destination)', label))
                    continue
                dst = project_path / destination
            else:
                dst = project_path / rel_source

            item_strategy = item.get('mergeStrategy', strategy)

            if not src.exists():
                actions.append(('skip (not found)', label))
                continue

            if dst.exists():
                if item_strategy == 'skip_if_exists' or (item_strategy == 'merge'):
                    actions.append(('skip (exists)', label))
                    continue
                elif files_differ(src, dst):
                    actions.append(('update', label))
                    if not dry_run:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                else:
                    actions.append(('unchanged', label))
            else:
                actions.append(('create', label))
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        # Sweep pass: files the manifest does not list are still part of the variant.
        # init-project.py installs them; sync must agree, or a custom variant whose manifest
        # lags behind its files would appear to sync cleanly while dropping components.
        sweep_dirs = {
            'agents': project_path / '.claude' / 'agents',
            'commands': project_path / '.claude' / 'commands',
            'tasks': project_path / '.claude' / 'tasks',
            'workflows': project_path / '.github' / 'workflows',
        }
        if component in sweep_dirs:
            src_dir = variant_dir / ('github-workflows' if component == 'workflows' else component)
            patterns = ('*.yml', '*.yaml') if component == 'workflows' else ('*.md',)
            listed = {
                Path(i['path'] if 'path' in i else i['source']).name
                for i in manifest_components.get(component, [])
                if i.get('path') or i.get('source')
            }
            sweep_srcs = sorted(s for pat in patterns for s in src_dir.rglob(pat)) if src_dir.exists() else []
            seen: Dict[str, Path] = {}
            for src in sweep_srcs:
                if src.name in listed:
                    continue
                if src.name in seen:
                    # The flat layout has room for one file per basename. Report rather than
                    # let sort order decide - and keep the same winner as init-project.py,
                    # or the two scripts would flip file content on alternating runs.
                    actions.append((
                        'skip (collision)',
                        f"{src.relative_to(variant_dir)} collides with "
                        f"{seen[src.name].relative_to(variant_dir)}"
                    ))
                    continue
                seen[src.name] = src
                dst = sweep_dirs[component] / src.name
                label = f"{src.name} (unlisted in manifest)"
                if dst.exists() and not files_differ(src, dst):
                    actions.append(('unchanged', label))
                    continue
                actions.append(('update' if dst.exists() else 'create', label))
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        results[component] = actions or [('skip', 'Not in variant')]

    return results


def print_sync_results(results: Dict[str, List[Tuple[str, str]]], dry_run: bool = False) -> None:
    """Print sync results in a readable format."""
    if dry_run:
        print("\n[DRY RUN - No changes made]\n")

    for component, actions in results.items():
        print(f"\n{component}:")
        for action, path in actions:
            icon = {
                'create': '  + ',
                'update': '  ~ ',
                'skip': '  - ',
                'skip (exists)': '  - ',
                'skip (variant override)': '  - ',
                'skip (collision)': '  ! ',
                'skip (no path/source)': '  ! ',
                'skip (no destination)': '  ! ',
                'skip (not found)': '  ! ',
                'unchanged': '  = ',
                'replace': '  * ',
                'error': '  ! ',
            }.get(action, '  ? ')
            print(f"{icon}{path} ({action})")


def main():
    parser = argparse.ArgumentParser(
        description='Sync Claude Workflow System components to a project'
    )
    parser.add_argument(
        'project_path',
        type=Path,
        help='Path to the target project'
    )
    parser.add_argument(
        '--components',
        '-c',
        nargs='+',
        default=['commands', 'agents', 'tasks', 'workflows'],
        choices=['commands', 'agents', 'tasks', 'workflows', 'templates'],
        help='Components to sync'
    )
    parser.add_argument(
        '--variant',
        '-v',
        type=str,
        help='Variant to sync (auto-detected if not specified)'
    )
    parser.add_argument(
        '--variant-path',
        type=Path,
        help='Path to a variant source directory in repo shape (manifest.json + agents/commands/tasks)'
    )
    parser.add_argument(
        '--strategy',
        '-s',
        choices=['overlay', 'replace', 'merge'],
        default='overlay',
        help='Sync strategy: overlay (default), replace, or merge'
    )
    parser.add_argument(
        '--base-only',
        action='store_true',
        help='Only sync base layer, skip variant'
    )
    parser.add_argument(
        '--variant-only',
        action='store_true',
        help='Only sync variant layer, skip base'
    )
    parser.add_argument(
        '--dry-run',
        '-n',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()
    project_path = args.project_path.resolve()

    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}")
        return 1

    # Resolve the variant source. An explicit --variant-path wins; otherwise the named
    # variant is looked up in this repository's variants/ directory. A variant authored
    # inside a project has no source tree, so there is nothing to resolve for those.
    variant_dir = args.variant_path.expanduser().resolve() if args.variant_path else None
    if variant_dir is not None and not (variant_dir / 'manifest.json').exists():
        print(f"Error: No manifest.json at {variant_dir}")
        return 1

    variant = args.variant
    if variant is None and variant_dir is not None:
        # An explicit --variant-path names the variant; it must win over whatever the
        # project's settings.json happens to say (often "base").
        variant = load_json(variant_dir / 'manifest.json').get('name', variant_dir.name)
    if variant is None:
        variant = detect_project_variant(project_path)

    # "base" (and an empty value) mean "no variant layer" - that is the normal state of a
    # base install, written by init-project.py as project.variant. Treating it as a variant
    # to resolve would make the documented `sync-workflow.py <project>` invocation fail.
    if variant is not None and variant.strip().lower() in ('', 'base', 'none'):
        variant = None

    print(f"Syncing Claude Workflow System to: {project_path}")
    print(f"Base version: {get_base_version()}")
    if variant:
        print(f"Variant: {variant}")
    print(f"Components: {', '.join(args.components)}")
    print(f"Strategy: {args.strategy}")

    had_error = False

    # Base components the active variant replaces. Without this the base layer re-adds a file
    # the variant overrode, the variant layer overwrites it again, and every run churns.
    exclusions = resolve_base_exclusions(project_path, variant_dir if variant else None)
    if variant and any(exclusions.values()):
        shown = {k: v for k, v in exclusions.items() if v}
        print("Base exclusions (%s): %s" % (
            variant, "; ".join(f"{k}: {', '.join(v)}" for k, v in shown.items())))

    # Sync base layer
    if not args.variant_only:
        print("\n--- Base Layer ---")
        base_results = sync_base_layer(
            project_path,
            args.components,
            args.strategy,
            args.dry_run,
            exclusions
        )
        print_sync_results(base_results, args.dry_run)

    # Sync variant layer
    if variant and not args.base_only:
        print(f"\n--- Variant Layer ({variant}) ---")
        variant_results = sync_variant_layer(
            project_path,
            variant,
            args.components,
            args.strategy,
            args.dry_run,
            variant_dir
        )
        print_sync_results(variant_results, args.dry_run)
        if 'error' in variant_results:
            had_error = True

    # A legacy .claude/variants/ tree holds inert components - merge them into the flat
    # layout. Non-destructive: nothing is overwritten and nothing is deleted.
    merge_legacy_variant_folder(project_path, args.dry_run)

    if had_error:
        print("\n✗ Sync finished with errors (see above).")
        return 1

    if not args.dry_run:
        print("\n✓ Sync completed!")
    else:
        print("\n[DRY RUN] No changes were made.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
