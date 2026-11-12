# Team Roster Guide

This folder holds `team-roster.md` — the configuration file that planning
commands read for team capacity, skills, and estimation. This guide explains
what every field means, which command uses it, and exactly what to update
when something changes. The behavioral source of truth is the `team-roster`
task (`.claude/tasks/team-roster.md`); this guide explains it for humans.

## How it fits together

```
/CyclePlan ─────────┐
/PRDFeasibility ────┤                      ┌── frontmatter (defaults & calibration)
/Breakdown ─────────┼──> team-roster task ──> team-roster.md ──┤
/PRDSequence ───────┘    (load / resolve /                     └── member blocks (per person)
                          deriveComposition)
```

Nothing about your team is hard-coded in the commands. Every number they use
comes from this folder's `team-roster.md`. Change the file, and the next
planning run picks it up — there is no cache or sync step.

The estimation model in one sentence: **work items are sized for an
imaginary "solid mid-level engineer working in their primary area"
(the 1.0 baseline), and every real person's estimate is that baseline
adjusted by their `velocityFactor` and, for work outside their primary
role, their skill proficiency.**

## Frontmatter reference (top of team-roster.md)

### `defaults` — capacity inputs

| Key | Shipped value | Used by | Meaning |
|-----|--------------|---------|---------|
| `hoursPerDay` | 6 | `/CyclePlan` capacity | Focused hours per person per working day (not 8 — meetings and reviews are already excluded) |
| `capacityPercent` | 80 | `/CyclePlan` capacity | Portion of those hours planned; the rest absorbs interrupts and unknowns |
| `workingDaysPerWeek` | 5 | `/CyclePlan` capacity | Converts cycle duration (`1w`/`2w`/`3w`) to working days |

**Capacity formula** (per person):

```
available hours = working days × hoursPerDay × (allocation/100) × (capacityPercent/100)
```

A member's own `hoursPerDay` (see member fields) overrides the default; the
`capacity` argument to `/CyclePlan` overrides `capacityPercent` for that run.

**Update when:** the team's meeting load changes (`hoursPerDay`), plans keep
over- or under-shooting (`capacityPercent`), or you move to 4-day weeks
(`workingDaysPerWeek`).

### `roleAbbreviations` — role vocabulary

Maps short codes to role names (`BE: backend`, `FE: frontend`, …). Every
member's `role` must map to one of these values. `/PRDFeasibility` uses the
codes when deriving a composition string like `"1 BE, 1 FE, 1 FS"`.

**Update when:** your team has a role the shipped list lacks (e.g.
`DA: data`). Add the pair here first, then use it in member blocks.

### `setupDefaults` — starting values for new members

Only used when *adding* a member (by `/SetupWorkflow`'s interactive fill-in,
or by you following the same convention). Never used at planning time.

| Key | Shipped value | Meaning |
|-----|--------------|---------|
| `velocityBySeniority` | junior 1.5, mid 1.0, senior 0.8, staff 0.7 | Starting `velocityFactor` per seniority — deliberately conservative; refine from actuals |
| `startingSkills` | primary 3, other 2 | Starting proficiency in the member's primary area vs. everything else |

**Update when:** your starting assumptions prove systematically wrong (e.g.
your juniors ramp faster than 1.5).

### `estimation.proficiencyMultipliers` — out-of-area penalties

Applied when a work item's area is **not** covered by the assignee's primary
role. The assignee's proficiency (1–5) in the item's area selects the
multiplier:

| Proficiency | Shipped multiplier | Effect on a 4h baseline item |
|-------------|-------------------|------------------------------|
| 4–5 | 1.0 | no penalty — they're effectively at home here |
| 3 | 1.25 | 4h → 5h before velocity |
| 2 | 1.5 | 4h → 6h before velocity |
| 1 or missing | `do-not-assign` | not a number: the item is flagged for reassignment or pairing, never silently assigned |

**Update when:** cross-area work consistently takes more or less than the
multipliers predict. Keep `do-not-assign` for level 1 unless you genuinely
want solo out-of-depth assignments.

## Member block reference (one per person)

Each member is a `## Name` heading, a yaml block, and a prose description.

| Field | Example | What it drives |
|-------|---------|----------------|
| `name` | `Alice` | The name used in planning commands (`team="Alice,Bob"`). Matched case-insensitively. A name not in the roster is planned at baseline (mid, 1.0, 100%) with an explicit warning — commands never invent abilities. |
| `role` | `backend` | The member's primary area. Work in this area gets **no** proficiency multiplier regardless of the skills matrix. Must map to a `roleAbbreviations` value. Feeds `/PRDFeasibility` composition and `/PRDSequence` role-supply contention. |
| `seniority` | `senior` | `junior \| mid \| senior \| staff`. Informational label plus the seed for `velocityFactor` at setup time. Changing it later does **not** change `velocityFactor` automatically — update both. |
| `velocityFactor` | `0.8` | The core estimation dial. `1.0` = the baseline mid-level engineer. **Lower is faster**: 0.8 means 20% faster (a 5h baseline item is planned at 4h); 1.5 means 50% slower (7.5h). Applied to every estimate for this person by `/CyclePlan` and `/Breakdown suggestAssignees`. |
| `allocation` | `100` | % of working time available to this team. Scales capacity (see formula) and weights composition: a member at 50% counts as half a person in `/PRDFeasibility` and `/PRDSequence`. |
| `hoursPerDay` | `# hoursPerDay: 6` | Optional per-person override of `defaults.hoursPerDay` (e.g. a part-time schedule). Uncomment to use. |
| `skills` | `frontend: 2` | Proficiency 1–5 per work area. Areas must match `/Breakdown` area labels: `backend`, `frontend`, `database`, `infrastructure`, `testing`. Drives assignee suggestion (prefer 4+, never assign at 1) and selects the out-of-area multiplier. |

**Skill scale:** 5 = expert / go-to person · 4 = works independently ·
3 = productive with occasional guidance · 2 = needs support · 1 = should
not work here solo.

**The prose description** (the paragraph under the yaml block) is read
verbatim by planning commands as estimation context. Cover: what this person
does, what they're strongest at, what to avoid assigning them, review
overhead they need or provide, and key-person risks. Keep it professional
and capability-focused — no compensation or performance-review language.

## The math, worked

Using the shipped example roster (Alice: senior BE, 0.8, 100% · Ben: mid FE,
1.0, 80% · Carla: junior FS, 1.5, 100%) with shipped defaults, for
`/CyclePlan duration="2w"`:

```
working days = 2 weeks × 5 = 10

Alice: 10 × 6 × 1.00 × 0.80 = 48.0h available
Ben:   10 × 6 × 0.80 × 0.80 = 38.4h available   (80% allocation)
Carla: 10 × 6 × 1.00 × 0.80 = 48.0h available
```

A frontend work item sized `4-6h` at baseline:

```
Ben   (FE primary, velocity 1.0):        4-6h × 1.0            = 4-6h
Alice (BE primary, frontend skill 2):    4-6h × 0.8 × 1.5      = 4.8-7.2h
Carla (FS primary covers frontend, 1.5): 4-6h × 1.5            = 6-9h
```

An infrastructure item considered for Carla (infrastructure skill 1):
**not assigned** — flagged for reassignment or pairing.

Plans always print the multipliers they applied (e.g.
`6-9h (4-6h baseline × 1.5 velocity)`) so you can audit any number back to
this file.

## Common updates

Every change gets a row in the Change Log table at the bottom of
`team-roster.md` — that history is what lets you audit why past plans
looked the way they did.

- **Someone joins** — copy any member block, fill in their values (seed
  `velocityFactor` from `setupDefaults.velocityBySeniority` and skills from
  `startingSkills`, or re-run `/SetupWorkflow` in update mode to be prompted).
  Log it.
- **Someone leaves** — delete their block, log it, and check other members'
  descriptions for key-person risks that just changed hands.
- **Role or allocation changes** — edit `role` / `allocation`, revisit the
  skills matrix if the primary area moved, log it.
- **Someone demonstrably levels up** — adjust `velocityFactor` and/or
  `skills` based on actuals from completed cycles (did their items
  consistently land under the adjusted estimates?), not on impressions.
  Update `seniority` and `velocityFactor` together. Log it.
- **Estimates are systematically off for everyone** — tune the frontmatter
  (`capacityPercent`, `proficiencyMultipliers`) rather than every member's
  `velocityFactor`. Log it.

## Errors and warnings you may see

| Message | Cause | Fix |
|---------|-------|-----|
| "No team roster found…" | `team-roster.md` missing | Run `/SetupWorkflow`, or copy the template from `base/templates/knowledge/team/` |
| "`{name}` is not in team-roster.md…" | A `team=` argument names someone unlisted | Add them as a member block |
| Member skipped with a parse warning | Malformed yaml in their block | Fix the yaml (watch indentation in `skills:`) |
| "Empty roster" error | No member blocks (or only unreplaced examples) | Add at least one real member |
| Fallback warning naming a frontmatter key | Roster predates a key (e.g. `estimation`) | Copy the missing block from the current template |
