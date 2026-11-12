#!/usr/bin/env python3
"""
Claude Workflow System - Project Initializer

Initializes a new project with the Claude Workflow System by:
1. Copying base layer components
2. Applying variant-specific configurations
3. Creating project structure
4. Setting up GitHub Actions workflows
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


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


def copy_directory(src: Path, dst: Path, exclude: Optional[List[str]] = None) -> None:
    """Copy directory contents, optionally excluding patterns."""
    exclude = exclude or []

    if not src.exists():
        print(f"Warning: Source directory does not exist: {src}")
        return

    for item in src.iterdir():
        if any(item.name.endswith(ex) or item.name == ex for ex in exclude):
            continue

        dst_item = dst / item.name

        if item.is_dir():
            dst_item.mkdir(parents=True, exist_ok=True)
            copy_directory(item, dst_item, exclude)
        else:
            dst_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst_item)


def process_template(template_path: Path, output_path: Path, variables: Dict[str, str]) -> None:
    """Process a template file, replacing variables."""
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for key, value in variables.items():
        content = content.replace(f'{{{{{key}}}}}', value)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove .template extension if present
    if output_path.suffix == '.template':
        output_path = output_path.with_suffix('')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def get_available_variants() -> List[str]:
    """Get list of available variants."""
    variants_dir = REPO_ROOT / 'variants'
    if not variants_dir.exists():
        return []

    variants = []
    for item in variants_dir.iterdir():
        if item.is_dir() and (item / 'manifest.json').exists():
            variants.append(item.name)

    return variants


def load_variant_manifest(variant_name: str) -> Optional[Dict]:
    """Load a variant's manifest file."""
    manifest_path = REPO_ROOT / 'variants' / variant_name / 'manifest.json'
    if not manifest_path.exists():
        return None
    return load_json(manifest_path)


def init_base_layer(project_path: Path) -> None:
    """Initialize the base layer in the project."""
    print("Initializing base layer...")

    base_dir = REPO_ROOT / 'base'

    # Copy commands
    commands_src = base_dir / 'commands'
    commands_dst = project_path / '.claude' / 'commands'
    if commands_src.exists():
        copy_directory(commands_src, commands_dst)
        print(f"  Copied commands to {commands_dst}")

    # Copy agents
    agents_src = base_dir / 'agents'
    agents_dst = project_path / '.claude' / 'agents'
    if agents_src.exists():
        copy_directory(agents_src, agents_dst)
        print(f"  Copied agents to {agents_dst}")

    # Copy tasks
    tasks_src = base_dir / 'tasks'
    tasks_dst = project_path / '.claude' / 'tasks'
    if tasks_src.exists():
        copy_directory(tasks_src, tasks_dst)
        print(f"  Copied tasks to {tasks_dst}")

    # Copy GitHub workflows
    workflows_src = base_dir / 'github-workflows'
    workflows_dst = project_path / '.github' / 'workflows'
    if workflows_src.exists():
        copy_directory(workflows_src, workflows_dst)
        print(f"  Copied GitHub workflows to {workflows_dst}")


def init_templates(project_path: Path, variables: Dict[str, str]) -> None:
    """Initialize template files in the project."""
    print("Initializing templates...")

    templates_dir = REPO_ROOT / 'base' / 'templates'

    for template_file in templates_dir.rglob('*.template'):
        relative_path = template_file.relative_to(templates_dir)
        output_path = project_path / relative_path

        # Remove .template extension
        output_path = output_path.with_suffix('')

        process_template(template_file, output_path, variables)
        print(f"  Created {output_path}")

    # Copy non-template files (like .gitkeep)
    for other_file in templates_dir.rglob('*'):
        if other_file.is_file() and not other_file.suffix == '.template':
            relative_path = other_file.relative_to(templates_dir)
            output_path = project_path / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(other_file, output_path)


def _apply_variant_components(project_path: Path, variant_dir: Path, manifest: Dict, variables: Dict[str, str]) -> Dict[str, List[str]]:
    """Apply variant components from a manifest, flattening into .claude/*.

    Returns the basenames installed per component type, so the caller can record provenance
    in .claude/workflow-manifest.json. That record is what lets /SubmitVariant later tell a
    handful of variant files apart from the ~60 base files sitting beside them.
    """
    # Process variant components based on manifest
    components = manifest.get('components', {})
    installed: Dict[str, List[str]] = {'agents': [], 'commands': [], 'tasks': [], 'workflows': []}

    # Copy variant agents (overlay with base)
    for agent in components.get('agents', []):
        src = variant_dir / agent['path']
        dst = project_path / '.claude' / 'agents' / Path(agent['path']).name
        if src.exists():
            shutil.copy2(src, dst)
            installed['agents'].append(dst.name)
            print(f"  Added variant agent: {agent['name']}")

    # Copy variant commands
    for command in components.get('commands', []):
        src = variant_dir / command['path']
        dst = project_path / '.claude' / 'commands' / Path(command['path']).name
        if src.exists():
            shutil.copy2(src, dst)
            installed['commands'].append(dst.name)
            print(f"  Added variant command: {command['name']}")

    # Copy variant tasks
    for task in components.get('tasks', []):
        src = variant_dir / task['path']
        dst = project_path / '.claude' / 'tasks' / Path(task['path']).name
        if src.exists():
            shutil.copy2(src, dst)
            installed['tasks'].append(dst.name)
            print(f"  Added variant task: {task['name']}")

    # Sweep pass: install component files the manifest does not list, and the variant's
    # CI workflows. Custom variants are frequently authored faster than their manifest is
    # updated; dropping those files silently is what makes a variant look "not installed".
    for comp_dir, dst_dir in (
        ('agents', project_path / '.claude' / 'agents'),
        ('commands', project_path / '.claude' / 'commands'),
        ('tasks', project_path / '.claude' / 'tasks'),
    ):
        src_dir = variant_dir / comp_dir
        if not src_dir.exists():
            continue
        listed = {Path(e['path']).name for e in components.get(comp_dir, []) if 'path' in e}
        seen: Dict[str, Path] = {}
        for src in sorted(src_dir.rglob('*.md')):
            if src.name in listed:
                continue
            if src.name in seen:
                # Two variant files share a basename; the flat layout has room for only one.
                # Installing whichever sorts last would be an arbitrary, silent choice.
                print(f"  WARNING: {src.relative_to(variant_dir)} collides with "
                      f"{seen[src.name].relative_to(variant_dir)} - keeping the first, "
                      f"skipping {src.relative_to(variant_dir)}")
                continue
            seen[src.name] = src
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_dir / src.name)
            installed[comp_dir].append(src.name)
            print(f"  Added variant {comp_dir[:-1]} (unlisted in manifest): {src.name}")

    workflows_src = variant_dir / 'github-workflows'
    if workflows_src.exists():
        workflows_dst = project_path / '.github' / 'workflows'
        for src in sorted(list(workflows_src.rglob('*.yml')) + list(workflows_src.rglob('*.yaml'))):
            workflows_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, workflows_dst / src.name)
            installed['workflows'].append(src.name)
            print(f"  Added variant workflow: {src.name}")

    # Copy variant templates
    for template in components.get('templates', []):
        src = variant_dir / template['source']
        dst = project_path / template['destination']

        strategy = template.get('mergeStrategy', 'skip_if_exists')

        if dst.exists() and strategy == 'skip_if_exists':
            print(f"  Skipped (exists): {dst}")
            continue

        if src.exists():
            if src.is_dir():
                copy_directory(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.suffix == '.template':
                    process_template(src, dst, variables)
                else:
                    shutil.copy2(src, dst)
            print(f"  Created: {dst}")

    return installed


def init_variant(project_path: Path, variant_name: str, variables: Dict[str, str]) -> Dict[str, List[str]]:
    """Initialize variant-specific components."""
    print(f"Initializing variant: {variant_name}")

    manifest = load_variant_manifest(variant_name)
    if not manifest:
        print(f"  Warning: Could not load manifest for variant {variant_name}")
        return {}

    variant_dir = REPO_ROOT / 'variants' / variant_name

    return _apply_variant_components(project_path, variant_dir, manifest, variables)


def init_variant_from_path(project_path: Path, variant_dir: Path, variables: Dict[str, str]) -> Dict[str, List[str]]:
    """Initialize variant-specific components from an arbitrary directory."""
    print(f"Initializing variant from path: {variant_dir}")

    manifest_path = variant_dir / 'manifest.json'
    if not manifest_path.exists():
        print(f"  Warning: Could not load manifest at {manifest_path}")
        return {}

    manifest = load_json(manifest_path)

    return _apply_variant_components(project_path, variant_dir, manifest, variables)


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


def create_directory_structure(project_path: Path) -> None:
    """Create the basic directory structure."""
    directories = [
        '.claude/commands',
        '.claude/agents',
        '.claude/tasks',
        '.github/workflows',
        'docs/planning',
        'docs/specs',
        'docs/reports',
        'knowledge/prd',
        'knowledge/architecture',
        'knowledge/team',
    ]

    for dir_path in directories:
        (project_path / dir_path).mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description='Initialize a project with Claude Workflow System'
    )
    parser.add_argument(
        'project_path',
        type=Path,
        nargs='?',
        help='Path to the project to initialize (not required with --list-variants)'
    )
    variant_group = parser.add_mutually_exclusive_group()
    variant_group.add_argument(
        '--variant',
        '-v',
        type=str,
        help='Variant to use (e.g., nextjs-development)'
    )
    variant_group.add_argument(
        '--variant-path',
        type=Path,
        help='Path to a custom variant layer directory to apply (overlay)'
    )
    parser.add_argument(
        '--name',
        '-n',
        type=str,
        help='Project name (defaults to directory name)'
    )
    parser.add_argument(
        '--description',
        '-d',
        type=str,
        default='A project using Claude Workflow System',
        help='Project description'
    )
    parser.add_argument(
        '--force',
        '-f',
        action='store_true',
        help='Overwrite existing files'
    )
    parser.add_argument(
        '--list-variants',
        action='store_true',
        help='List available variants and exit'
    )

    args = parser.parse_args()

    # List variants if requested
    if args.list_variants:
        variants = get_available_variants()
        if variants:
            print("Available variants:")
            for v in variants:
                manifest = load_variant_manifest(v)
                desc = manifest.get('description', 'No description') if manifest else 'No description'
                print(f"  {v}: {desc}")
        else:
            print("No variants available")
        return 0

    if args.project_path is None:
        parser.error('project_path is required unless --list-variants is given')

    project_path = args.project_path.resolve()

    # Check if project already has workflow system
    if (project_path / '.claude').exists() and not args.force:
        print(f"Error: Project already has .claude directory. Use --force to overwrite.")
        return 1

    # Resolve variant identity for template variables. When a custom variant
    # path is given, read its manifest to source PROJECT_TYPE / VARIANT_NAME.
    requested_variant = args.variant
    if requested_variant and requested_variant not in get_available_variants():
        print(f"Error: Variant '{requested_variant}' not found in {REPO_ROOT / 'variants'}.")
        print(f"       Available: {', '.join(get_available_variants()) or '(none)'}")
        return 1

    variant_type = args.variant or 'generic'
    variant_label = args.variant or 'base'
    if not args.variant and args.variant_path:
        custom_manifest_path = args.variant_path.expanduser().resolve() / 'manifest.json'
        if custom_manifest_path.exists():
            custom_manifest = load_json(custom_manifest_path)
            variant_label = custom_manifest.get('name', args.variant_path.name)
            variant_type = custom_manifest.get('projectType', variant_label)

    # Prepare template variables
    project_name = args.name or project_path.name
    variables = {
        'PROJECT_NAME': project_name,
        'PROJECT_DESCRIPTION': args.description,
        'PROJECT_TYPE': variant_type,
        'VARIANT_NAME': variant_label,
        'TIMESTAMP': '',  # Will be filled dynamically
        'SESSION_ID': '',
        'PROJECT_STRUCTURE': '# See project documentation',
        'PREREQUISITES': '# See project documentation',
        'INSTALLATION_COMMANDS': '# See project documentation',
        'DEV_SERVER_COMMAND': '# See project documentation',
        'TEST_COMMAND': '# See project documentation',
        'BUILD_COMMAND': '# See project documentation',
        'TASK_MANAGEMENT_TOOL': 'Linear',
        'ADDITIONAL_CONTEXT': '',
    }

    print(f"\nInitializing Claude Workflow System for: {project_name}")
    print(f"Project path: {project_path}")
    if args.variant:
        print(f"Variant: {args.variant}")
    print()

    # Create directory structure
    create_directory_structure(project_path)

    # Initialize base layer
    init_base_layer(project_path)

    # Initialize templates
    init_templates(project_path, variables)

    # Initialize variant if specified
    applied_variant = 'base'
    variant_files: Dict[str, List[str]] = {}
    variant_meta: Optional[Dict] = None
    if args.variant:
        if args.variant not in get_available_variants():
            print(f"Error: Variant '{args.variant}' not found in {REPO_ROOT / 'variants'}.")
            print(f"       Available: {', '.join(get_available_variants()) or '(none)'}")
            return 1
        else:
            variant_files = init_variant(project_path, args.variant, variables)
            variant_meta = load_variant_manifest(args.variant)
            applied_variant = args.variant
    elif args.variant_path:
        variant_dir = args.variant_path.expanduser().resolve()
        manifest_path = variant_dir / 'manifest.json'
        if not manifest_path.exists():
            print(f"Error: No manifest.json at {variant_dir}.")
            return 1
        else:
            variant_files = init_variant_from_path(project_path, variant_dir, variables)
            variant_meta = load_json(manifest_path)
            applied_variant = variant_meta.get('name', variant_dir.name)

    # A legacy .claude/variants/ tree holds inert components - merge them into the flat
    # layout. Nothing is deleted; the folder is reported and left for the user to remove.
    merge_legacy_variant_folder(project_path)

    # Write the installation manifest: the project's record of what was installed and, for
    # every file, which layer it came from. /SubmitVariant reads this to reconstruct a
    # variants/<name>/ folder containing only the variant's own files.
    version_file = REPO_ROOT / 'base' / 'VERSION'
    base_version = version_file.read_text(encoding='utf-8').strip() if version_file.exists() else 'unknown'

    component_dirs = {
        'agents': project_path / '.claude' / 'agents',
        'commands': project_path / '.claude' / 'commands',
        'tasks': project_path / '.claude' / 'tasks',
        'workflows': project_path / '.github' / 'workflows',
    }
    base_source_dirs = {
        'agents': REPO_ROOT / 'base' / 'agents',
        'commands': REPO_ROOT / 'base' / 'commands',
        'tasks': REPO_ROOT / 'base' / 'tasks',
        'workflows': REPO_ROOT / 'base' / 'github-workflows',
    }
    components: Dict[str, List[Dict[str, str]]] = {}
    for comp, comp_dir in component_dirs.items():
        entries = []
        if comp_dir.exists():
            owned = set(variant_files.get(comp, []))
            from_base = {f.name for f in base_source_dirs[comp].glob('*') if f.is_file()}
            for f in sorted(comp_dir.iterdir()):
                if not f.is_file():
                    continue
                if f.name in owned:
                    layer = 'variant'
                elif f.name in from_base:
                    layer = 'base'
                else:
                    # Present before this run and installed by neither layer - the user's own
                    # file. Recording it as "base" would be a lie, and would let a private file
                    # be swept into a public PR by the derived-provenance rule.
                    layer = 'local'
                entries.append({'file': f.name, 'layer': layer})
        components[comp] = entries

    workflow_manifest = {
        'schemaVersion': 1,
        'generatedBy': f'init-project.py (claude-workflow {base_version})',
        'baseVersion': base_version,
        'installedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'components': components,
    }
    if applied_variant != 'base':
        workflow_manifest['variant'] = {
            'name': applied_variant,
            'origin': 'repo' if args.variant else 'custom',
            'description': (variant_meta or {}).get('description', ''),
            'projectType': (variant_meta or {}).get('projectType', ''),
            'version': (variant_meta or {}).get('version', '1.0.0'),
        }
        if (variant_meta or {}).get('baseExclusions'):
            workflow_manifest['baseExclusions'] = variant_meta['baseExclusions']

    manifest_file = project_path / '.claude' / 'workflow-manifest.json'
    manifest_file.write_text(json.dumps(workflow_manifest, indent=2) + '\n', encoding='utf-8')
    print(f"  Wrote installation manifest: {manifest_file}")

    # Keep the legacy marker for tooling that still reads it.
    marker = project_path / '.claude' / '.workflow-version'
    marker.write_text(json.dumps({
        'baseVersion': base_version,
        'variant': applied_variant,
    }, indent=2) + '\n', encoding='utf-8')

    print("\n✓ Claude Workflow System initialized successfully!")
    print("\nNext steps:")
    print("  1. Review and customize CLAUDE.md")
    print("  2. Configure .claude/settings.json for your project")
    print("  3. Add ANTHROPIC_API_KEY to GitHub secrets for CI workflows")
    print("  4. Run /StartSession to begin your first development session")

    return 0


if __name__ == '__main__':
    sys.exit(main())
