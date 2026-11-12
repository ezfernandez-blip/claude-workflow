***

**CLIENT REPOSITORY NOTICE**

**Prepared for: Svitla Systems**

This repository is provided as a starter project for your team to own, manage,
and modify based on your training. Going forward, your team is fully responsible
for all maintenance, customization, and support of this codebase.

| | |
|---|---|
| **Version** | Workflow System v2.4.0 |
| **Support Contact** | Johann Beukes (j.beukes@svitla.com) |
| **Original Creator** | Johann Beukes (johann@red-blue.ai) — Attribution only, not for support |
| **License** | Apache 2.0 — See LICENSE and NOTICE files |

**DISCLAIMER**: This software is provided "AS IS" without warranties of any kind,
express or implied. There are no guarantees of fitness for any particular purpose.
Your team is solely responsible for determining its appropriateness for your use.
See the LICENSE file for complete terms.

***

# Claude Workflow System

![Workflow System](https://img.shields.io/badge/Workflow_System-2.4.0-blue) ![Plugin](https://img.shields.io/badge/Plugin-1.3.0-green) ![License](https://img.shields.io/badge/License-Apache_2.0-yellow)

A modular, extensible workflow system for Claude Code that provides structured development workflows, CI/CD integration, and project-type-specific variants.

## Overview

The Claude Workflow System gives you:

- **Structured Development Workflows**: Commands for session management, feature implementation, bug fixing, and code review
- **Intelligent Agents**: AI specialists for code writing, testing, documentation, and review
- **CI/CD Integration**: GitHub Actions for automated code and security reviews
- **Project Variants**: Specialized configurations for different project types (Next.js, Python, etc.)

### What's New in v2.4.0

Variants have two shapes, and this release makes the distinction explicit:

- **The repository** keeps each variant as `variants/<name>/` — the unit a pull request reviews and versions.
- **A project** holds the merged flat result (`.claude/{agents,commands,tasks}`, `.github/workflows/`) plus `.claude/workflow-manifest.json`, which tags every installed component `"layer": "base"`, `"layer": "variant"`, or `"layer": "local"` (a file that was already there and that neither layer installed — yours). A project never mirrors the repository shape.
- **A variant authored inside a project has no folder at all.** `/SubmitVariant` reads the manifest, builds a temporary `variants/<name>/` folder in repo shape, opens the PR, and deletes it again.
- **The legacy-layout repair is non-destructive** — components are merged out of a `.claude/variants/` tree without overwriting anything, and the folder is left for you to remove.
- **Specialists win by routing, not by deletion.** Variants no longer exclude base agents. `code-writer` stays installed; each variant's `ImplementFeature`/`FixBug`/`RefactorCode` carries an Agent Routing table that prefers the variant's specialists for work in their domain and falls back to `code-writer` for generic code none of them covers. Exclusions now apply only to same-named overlays (a command or task the variant replaces).
- **Windows fixes** — scripts no longer crash on console encoding or on reading UTF-8 variant files; `validate-variant.py` could previously not read three of the four bundled variants.

### What's New in v2.3.0

- **Team Roster Configuration** — Planning commands (`/CyclePlan`, `/PRDFeasibility`, `/Breakdown`, `/PRDSequence`) now load team composition from a persistent roster at `knowledge/team/team-roster.md` instead of ad-hoc `team=` strings. The roster captures each member's role, seniority, velocity multiplier, allocation, and skills, so estimates are adjusted per person and plans stay auditable. See [Team Roster Configuration](#team-roster-configuration) below.
- **Assignee Suggestions** — `/Breakdown suggestAssignees=true` picks a best-fit assignee per Work Item from the roster skills matrix and shows adjusted estimates.
- **Backward Compatible** — Every planning command still accepts its `team` argument; provided names are resolved against the roster, and unknown names are planned at a documented baseline with a warning.

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## Installation Methods

Choose the method that works best for you:

| Method | Best For | Requirements |
|--------|----------|--------------|
| **Claude Code Plugin** | Most users - simple 3-step setup | Claude Code CLI, Git |
| **Python Scripts** | Automation, CI/CD pipelines | Python 3.8+, Git |

---

## Method 1: Claude Code Plugin (Recommended)

The plugin provides an interactive setup experience directly within Claude Code.

### Step 1: Add the Marketplace and Install the Plugin

In Claude Code, first add the Svitla Systems workflows marketplace:

```
/plugin marketplace add https://github.com/svitla-internal/claude-workflow-plugin.git
```

Then install the plugin:

```
/plugin install claude-workflow@svitla-internal-workflows
```

**Alternative: Test locally** (for plugin development):
```bash
git clone https://github.com/svitla-internal/claude-workflow-plugin.git
claude --plugin-dir /path/to/claude-workflow-plugin
```

### Step 2: Set Up a New Project

Navigate to your project directory (new or existing) and run:

```
/claude-workflow:setup
```

The plugin will:
1. Fetch the latest workflow system from GitHub
2. Detect if it's a new project or existing setup
3. Ask you to select a variant (base, nextjs-development, etc.)
4. Copy all necessary files to your project
5. Generate customized CLAUDE.md and configuration

### Step 3: Start Using Workflows

After setup, you have access to all workflow commands:

```
/StartSession          # Begin a development session
/ImplementFeature      # Start feature implementation
/FixBug               # Investigate and fix bugs
/ReviewCode           # Request code review
/EndSession           # End session, optionally trigger CI
```

### Plugin Commands Reference

| Command | Description |
|---------|-------------|
| `/claude-workflow:setup` | Set up workflow system in current directory |
| `/claude-workflow:update` | Update existing installation to latest version |
| `/claude-workflow:variants` | List available project variants |
| `/claude-workflow:status` | Check current installation status |

> **Note**: The plugin itself is NOT installed into your project. It's the "installer" that fetches and sets up the workflow components.

For detailed plugin documentation, see the [Plugin Repository](https://github.com/svitla-internal/claude-workflow-plugin).

---

## Method 2: Python Scripts

Use Python scripts for automated or scripted installations.

### Prerequisites

- Python 3.8 or later
- Git

### Initialize a New Project

```bash
# Clone this repository (one-time)
git clone https://github.com/svitla-internal/claude-workflow.git

# Initialize your project
python claude-workflow/scripts/init-project.py /path/to/your/project \
  --variant nextjs-development \
  --name "My Project" \
  --description "Project description"
```

### Update an Existing Project

```bash
python claude-workflow/scripts/sync-workflow.py /path/to/your/project \
  --variant nextjs-development
```

### List Available Variants

```bash
python claude-workflow/scripts/init-project.py --list-variants
```

### Script Options

Both `init-project.py` and `sync-workflow.py` accept `--variant-path <dir>` to apply a variant from
any source directory instead of a name resolved inside `variants/`.


**init-project.py**:
```
--variant, -v     Variant to use (e.g., nextjs-development)
--name, -n        Project name (defaults to directory name)
--description, -d Project description
--force, -f       Overwrite existing files
--list-variants   List available variants and exit
```

**sync-workflow.py**:
```
--variant, -v      Variant to sync
--components, -c   Components to sync (commands, agents, tasks, workflows)
--strategy, -s     Sync strategy (overlay, replace, merge)
--base-only        Only sync base layer
--variant-only     Only sync variant layer
--dry-run, -n      Preview changes without applying
```

### Upgrading Zip-Delivered Copies

If you distribute this repository as a zip file, ship version upgrades as a self-applying package instead of a full re-delivery.

**Maintainer** — build the package from git history (collects every file that changed between the two versions, plus the release notes as the commit message):

```bash
python scripts/create-upgrade-package.py --from <ref-of-their-version>
# -> dist/claude-workflow-upgrade-2.2.5-to-2.3.0.zip
```

**Recipient** — unzip and run the bundled applier against their copy:

```bash
python apply-upgrade.py /path/to/their/claude-workflow
```

The applier verifies their current version matches the package baseline (refusing on mismatch unless `--force`), copies updates, applies deletions and renames, bumps `base/VERSION`, and — when the copy is a git repository — commits with the release message (`--push` to also push, `--no-commit` to skip, `--dry-run` to preview). Non-git copies get the files with a note to commit wherever they track changes.

---

## What Gets Installed

When you set up a project, the following structure is created:

```
your-project/
├── .claude/
│   ├── commands/           # 29 workflow commands
│   │   ├── StartSession.md
│   │   ├── EndSession.md
│   │   ├── ImplementFeature.md
│   │   └── ...
│   ├── agents/             # 10+ AI agents
│   │   ├── code-writer.md
│   │   ├── reviewer.md
│   │   └── ...
│   ├── tasks/              # 21 orchestration tasks
│   │   ├── session-management.md
│   │   ├── ci-integration.md
│   │   └── ...
│   └── workflow-manifest.json  # what was installed, and which layer each file came from
├── .github/
│   └── workflows/
│       ├── code-review.yml     # AI code review on PRs
│       └── security-review.yml # Security analysis on PRs
├── docs/
│   ├── planning/           # Session state and plans
│   └── specs/              # Technical specifications
├── knowledge/
│   ├── prd/                # Product requirements
│   ├── architecture/       # Architecture documentation
│   └── team/
│       └── team-roster.md  # Team roster for planning commands
└── CLAUDE.md               # Project guidance for Claude
```

The layout is **flat**: base and variant components sit side-by-side in the same three
directories, and `.claude/workflow-manifest.json` records which layer each file came from. A
variant never gets its own folder in a project — that per-variant shape belongs to this repository,
where it is the unit a pull request reviews. If a project does contain `.claude/variants/` (from a
pre-2.4.0 install), the installers merge its components into the flat directories and leave the
folder for you to remove.

---

## Available Variants

| Variant | Type | Description |
|---------|------|-------------|
| `base` | Generic | Core workflow system for any project |
| `nextjs-development` | Next.js | Full-stack Next.js with App Router, React, TypeScript |
| `electron-desktop` | Electron | Electron desktop app development with React renderer, TypeScript, and electron-builder |
| `ml-distillation` | Python | ML/AI R&D for model distillation, evaluation, benchmarking, and experiment workflows |

### Base Variant

Includes all core components - suitable for any project type:
- 29 commands for development workflows
- 10 agents for code, docs, testing, review, planning
- 21 tasks for orchestration
- GitHub Actions for CI/CD

### Next.js Variant

Extends base with Next.js specializations:
- **Additional Agents**: nextjs-specialist, react-component-writer, api-route-designer
- **Additional Commands**: /CreateComponent, /CreateAPIRoute
- **Additional Tasks**: nextjs-build
- **Templates**: Next.js-specific CLAUDE.md

### Electron Desktop Variant

Extends base with Electron specializations:
- **Additional Agents**: electron-specialist, ipc-architect
- **Additional Commands**: /CreateComponent, /BuildInstaller, /RunElectronTests
- **Additional Tasks**: electron-build
- **Templates**: Electron-specific CLAUDE.md

### ML Distillation Variant

Extends base with ML/AI R&D specializations:
- **Additional Agents**: distillation-architect, eval-benchmark-specialist, experiment-documentarian
- **Additional Commands**: /RunExperiment, /EvalModel, /PublishModel, /SyncExperiments
- **Additional Tasks**: experiment-tracking, model-evaluation
- **Templates**: ML-specific CLAUDE.md

### Create Your Own Variant

Don't see a variant for your project type? Create one during setup:

```bash
# During /SetupWorkflow, select "Create New Variant"
# Or run directly:
/CreateVariant swift-ios
```

**Inside a project**, a variant has no folder. You author its components straight into
`.claude/agents/`, `.claude/commands/`, and `.claude/tasks/`, and they are tagged
`"layer": "variant"` in `.claude/workflow-manifest.json`. That manifest is what distinguishes them
from the base components beside them.

**Inside a clone of this repository**, a variant is a folder — `variants/<name>/` with its own
`manifest.json`, `README.md`, and component directories — because that is the unit a pull request
reviews and versions.

`/SubmitVariant` bridges the two: it reads the project manifest, materializes a temporary
`variants/<name>/` folder in repo shape, opens the PR, and removes the temporary folder afterwards.

```bash
/SubmitVariant swift-ios
```

All contributions go through branches and pull requests - never direct push to main.

---

## Core Commands

| Command | Description |
|---------|-------------|
| `/StartSession` | Initialize development session with context loading |
| `/EndSession` | Close session, persist state, optionally trigger CI |
| `/SessionStatus` | View current session state and progress |
| `/SetupProjectMeta` | Reconfigure Linear, Coda, and GitHub integrations |
| `/CreateVariant` | Create a new variant for unsupported project types |
| `/SubmitVariant` | Submit variant to community via branch and PR |
| `/ImplementFeature` | Guided feature implementation workflow |
| `/FixBug` | Bug investigation and fix workflow |
| `/ReviewCode` | AI-powered code review |
| `/GenerateTests` | Generate test specifications |
| `/RefactorCode` | Code refactoring workflow |
| `/RunSecurityAudit` | Security-focused code analysis |
| `/UpdateDocs` | Documentation management |
| `/PRDIntake` | Import PRD from Coda, Confluence, or local file |
| `/PRDValidate` | Validate PRD completeness with scoring |
| `/PRDEnrich` | Add technical context to PRD |
| `/PRDFeasibility` | Assess feasibility with resource estimates |
| `/PRDSequence` | Sequence multiple initiatives |
| `/Breakdown` | Convert PRD to sized work items |
| `/CyclePlan` | Plan capacity-aware development cycle |
| `/CycleCommit` | Commit cycle plan to Linear |
| `/CycleStatus` | Get cycle progress and blockers |
| `/CycleSummary` | Generate end-of-cycle summary |
| `/CycleRetro` | Retrospective analysis |

---

## Core Agents

| Agent | Description |
|-------|-------------|
| `code-writer` | Full-stack engineer for production-ready code |
| `reviewer` | Code review specialist with security awareness |
| `test-planner` | Test specification and strategy expert |
| `doc-writer` | Technical documentation specialist |
| `schema-designer` | Database architecture expert |
| `researcher` | Standards and compliance researcher |
| `prd-validator` | PRD structure validation and completeness scoring |
| `technical-analyst` | Codebase analysis for PRD enrichment and feasibility |
| `cycle-planner` | Capacity planning and cycle management |
| `status-aggregator` | Status reporting and retrospective analysis |

---

## Post-Installation Setup

### 1. Configure CLAUDE.md

Review and customize the generated `CLAUDE.md` with:
- Your project description
- Repository structure
- Development guidelines
- Environment setup instructions

### 2. Project Integrations (Configured During Setup)

During setup, you'll be prompted to configure:
- **Linear**: Select team and project for issue tracking
- **Coda**: Choose document and page for product requirements
- **GitHub**: Verify repository access (auto-detected from git remote)

To reconfigure later, run `/SetupProjectMeta`.

### 3. Set Up GitHub Actions

Add your Anthropic API key to GitHub secrets:

1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key

### 4. Configure the Team Roster

Fill in `knowledge/team/team-roster.md` with your real team — `/SetupWorkflow` offers an interactive fill-in during setup, or edit the file directly. Planning commands require at least one real member. See [Team Roster Configuration](#team-roster-configuration) below.

### 5. Start Your First Session

```
/StartSession
```

The session will verify your project integrations are configured and ready.

---

## Team Roster Configuration

Planning commands read team composition from a single configuration file in your project: [`knowledge/team/team-roster.md`](base/templates/knowledge/team/team-roster.md.template) (link goes to the shipped template). It defines each team member's name, role, seniority, velocity multiplier, allocation, and per-area skill proficiency, plus a short prose description — the source of truth that `/CyclePlan`, `/PRDFeasibility`, `/Breakdown`, and `/PRDSequence` use for capacity and estimation.

A complete field-by-field reference — what every setting means (capacity, velocity, proficiency, skill descriptions), which command uses it, the exact math, and what to update when the team changes — ships alongside the roster as the **[Team Roster Guide](base/templates/knowledge/team/README.md)**, installed at `knowledge/team/README.md` in your project.

**Initial setup (via skills):** the roster is created during `/SetupWorkflow` (step "Configure Team Roster"). The template ships pre-populated with three example members (a senior specialist, a partially-allocated mid, a junior generalist) so the format is self-explanatory. The skill copies it into your project and offers an interactive fill-in that replaces the examples — for each member you provide a name, primary role, and seniority, and starting values come from the template's own `setupDefaults` frontmatter (nothing is hard-coded in the skills), to be refined over time. You can skip this step, but planning commands require at least one real member before they will plan.

**Updating after the project starts:** when someone joins or leaves the team, changes role, or demonstrably levels up, edit `knowledge/team/team-roster.md` directly — add or remove the member's block, adjust their values, and record the change in the roster's built-in Change Log table so plans stay auditable. Existing projects that predate 2.3.0 get the roster by re-running `/SetupWorkflow` in update mode, which offers to add `knowledge/team/` if it's missing. Unknown names passed to planning commands are never invented into roles; they are planned at a documented baseline with a warning until you add them to the roster.

---

## Repository Structure

```
claude-workflow/                     # This repository
├── base/                           # Core workflow system
│   ├── commands/                   # Base commands (29 files)
│   ├── agents/                     # Base agents (10 files)
│   ├── tasks/                      # Base tasks (21 files)
│   ├── github-workflows/           # CI/CD templates
│   ├── templates/                  # Project templates
│   ├── schema/                     # Variant manifest schema
│   └── VERSION                     # Base version
├── variants/                       # Project-type extensions
│   ├── nextjs-development/         # Next.js variant
│   ├── electron-desktop/           # Electron desktop variant
│   └── ml-distillation/            # ML/AI R&D variant
│       ├── manifest.json
│       ├── agents/
│       ├── commands/
│       ├── tasks/
│       └── templates/
├── scripts/                        # Python installation scripts
│   ├── init-project.py
│   ├── sync-workflow.py
│   ├── validate-variant.py
│   ├── merge-layers.py
│   ├── create-upgrade-package.py   # Build upgrade zip for zip-delivered copies
│   └── apply-upgrade.py            # Bundled into the zip; applies the upgrade
└── docs/                          # Repository documentation
    ├── getting-started.md
    ├── architecture.md
    └── creating-variants.md
```

**Plugin**: The Claude Code plugin lives in a separate repository: [claude-workflow-plugin](https://github.com/svitla-internal/claude-workflow-plugin)

**Installed in your project**: `base/` and selected `variants/` content

**NOT installed**: `scripts/`, `docs/` (these are tools, not project content)

---

## Documentation

- [Getting Started Guide](docs/getting-started.md) - Detailed setup walkthrough
- [Architecture](docs/architecture.md) - System design and concepts
- [Team Roster Guide](base/templates/knowledge/team/README.md) - Field-by-field reference for the team configuration file
- [Changelog](CHANGELOG.md) - Version history
- [Creating Variants](docs/creating-variants.md) - Build custom variants
- [Plugin Documentation](https://github.com/svitla-internal/claude-workflow-plugin) - Plugin installation and usage (separate repo)

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Claude Code | Required |
| Git | Required (for fetching from GitHub) |
| Python | 3.8+ (only for scripts method) |
| GitHub | For CI/CD workflows |
| Node.js | 18+ (for Next.js variant) |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Support

- [GitHub Issues](https://github.com/svitla-internal/claude-workflow/issues)
- [Documentation](docs/)
