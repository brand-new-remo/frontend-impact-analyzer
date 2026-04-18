# Frontend Impact Analyzer Handoff

This document captures the current project state, design decisions, known context, and recommended next work. It is intended for a future tool or agent continuing from a fresh context.

## Product Goal

This repository is a Claude/Codex skill plus Python analyzer for front-end change impact analysis.

Target usage:

- User opens Claude Code in a real React/Vite/React Router project.
- User invokes this skill.
- Skill checks environment and project context.
- Skill can generate a git diff from two branches or read an existing diff.
- Python performs deterministic evidence collection and clustering.
- Claude Code performs per-cluster semantic analysis.
- Python merges and validates cluster results.
- Claude optionally refines final cases without changing intent or scope.

Main user scenario:

- The user's wife is a QA/test development engineer.
- She uses Claude Code on Windows.
- She wants to pass branch/diff + repo wiki + project profile + requirements + specs and receive precise, evidence-backed QA cases.
- Previous versions generated generic template-like cases such as "User List Page 页面基础回归"; this is explicitly considered a failure mode.

Core principle:

```text
Python collects evidence and validates structure.
Claude performs evidence-constrained semantic judgment and wording.
No final QA case should be produced without cluster-level Claude analysis.
```

## Current Architecture

High-level workflow:

```text
doctor/preflight
-> diff generation or diff reading
-> diff parsing and noise classification
-> project scan with AST/import graph/routes
-> impact seeds
-> change clusters
-> cluster-context evidence packs
-> Claude writes cluster-analysis/*.analysis.json
-> Python merges into 99-merged-result.json
-> Claude case-refiner optionally writes 99-refined-cases.json
```

Important files:

- `SKILL.md`: skill entry instructions.
- `scripts/front_end_impact_analyzer.py`: CLI orchestrator.
- `scripts/analyzer/workflow.py`: config, preflight, doctor, diff generation, run dirs, Claude agent installation.
- `scripts/analyzer/diff_parser.py`: parses git diff, semantic tags, API field heuristics, noise classification hook.
- `scripts/analyzer/noise_classifier.py`: skips non-logic changes such as format-only, comment-only, import-only, style/test/generated/lockfile.
- `scripts/analyzer/global_change_classifier.py`: isolates global/cross-cutting changes instead of expanding to every page.
- `scripts/analyzer/project_scanner.py`: AST scan, import graph, reverse imports, route parsing, nested routes, lazy imports, route comments/meta titles.
- `scripts/analyzer/context_collector.py`: builds `cluster-context/*.json`, including diff/code/doc/route/trace/flow/comment evidence.
- `scripts/analyzer/cluster_builder.py`: builds diff index, impact seeds, clusters, coverage.
- `scripts/analyzer/cluster_tasks.py`: writes `06-cluster-analysis-tasks.md`.
- `scripts/analyzer/result_merger.py`: merges Claude cluster analyses and runs validation.
- `scripts/analyzer/cluster_analysis_validator.py`: flags generic/unsupported/unclear/high-confidence-without-code cases.
- `agents/claude/*.md`: Claude Code subagent templates.
- `schemas/*.json`: JSON contracts.
- `references/*.md`: support docs read on demand.
- `internal/*.md`: internal design, review, and handoff docs.

Deprecated/kept for compatibility:

- `scripts/analyzer/case_builder.py` is deprecated. Python should not generate final template QA cases.

## Runtime And Command Rules

The skill should be run through `uv`.

Reason:

- Claude Code usually runs inside the target business repo.
- Analyzer code and Python dependencies live in this skill repo.
- `uv run --project "<skill_root>" ...` lets the current working directory be anything while using the skill's Python dependency context.

Canonical command form:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" ...
```

Windows/PowerShell:

- The user is expected to run on Windows.
- Commands in docs are one-line with quoted paths.
- Do not use Bash `\` continuations in PowerShell.
- PowerShell line continuation uses backticks, but the docs intentionally prefer one-line commands.

Doctor command:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --doctor
```

`--doctor` checks:

- `uv` is installed.
- Python is `>=3.12`.
- `tree_sitter` imports.
- `tree_sitter_typescript` imports.
- `<skill_root>` looks like this skill root.
- target project root is a git worktree.

If `uv` is missing, Claude should stop and ask the user to install uv. Do not guess a non-uv fallback unless the user explicitly asks for it.

## Run Artifact Policy

Current desired behavior:

- Each run gets its own independent run directory.
- All process artifacts and result artifacts live together inside that run directory.
- Root-level output files should not be written by default.

Default run artifacts:

```text
<outputDir>/<runId>/
├── 00-run-manifest.json
├── 01-preflight-report.json
├── 02-document-index.json
├── 03-diff-index.json
├── 04-file-impact-seeds.json
├── 05-change-clusters.json
├── 06-cluster-analysis-tasks.md
├── cluster-context/
├── cluster-analysis/
├── 90-coverage-report.json
├── 98-analysis-state.json
├── 99-final-result.json
├── 99-merged-result.json
└── 99-refined-cases.json
```

Notes:

- `99-final-result.json` is the initial analysis package. It has empty `cases` before Claude cluster analysis.
- `99-merged-result.json` is created after `--merge-cluster-analysis`.
- `99-refined-cases.json` is written by Claude `case-refiner`, not by Python.
- `--state-output` and `--result-output` are optional export copies only.

## Config And Preflight

Default config file in target project:

```text
impact-analyzer.config.json
```

Important config fields:

- `paths.repoWikiDir`
- `paths.projectProfileFile`
- `paths.requirementsDir`
- `paths.specsDir`
- `paths.diffDir`
- `paths.outputDir`
- `diff.ignoreDirs`
- `diff.ignoreFiles`
- `diff.ignoreGlobs`
- `analysis.requireRepoWiki`
- `analysis.requireRequirements`
- `analysis.requireSpecs`
- `analysis.maxClusterContextChars`
- `analysis.maxCommentEvidencePerCluster`

Preflight behavior:

- Required missing context should block analysis.
- If repo wiki is required but missing, tell the user to generate it with the repo-wiki skill before continuing.
- The CLI now writes blocked result/state into the run dir and exits instead of continuing with weak evidence.

## Diff Handling

Diff generation command:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --make-diff --base-branch "<base_branch>" --compare-branch "<compare_branch>"
```

Diff names:

```text
diff_<base>_to_<compare>_<YYYYMMDD_HHMMSS>.patch
```

Large diff concern:

- Real diffs can be around 50k lines.
- Do not put full diff into one LLM prompt.
- The analyzer indexes, classifies, clusters, and creates bounded per-cluster context packs.

Noise handling:

- High-confidence non-logic changes are visible in `03-diff-index.json` and coverage but not traced/clustered.
- Noise kinds include:
  - `format-only`
  - `comment-only`
  - `import-only`
  - `type-only`
  - `text-only`
  - `style-only`
  - `test-only`
  - `generated-file`
  - `lockfile`
  - `logic-change`

Global change handling:

- Global/cross-cutting files become separate global clusters.
- They should be analyzed through representative flows.
- They should not expand to every page.

## Evidence Packs

Each `cluster-context/<clusterId>.json` contains:

- `diffEvidence`
- `traceEvidence`
- `routeEvidence`
- `flowHints`
- `codeEvidence`
- `commentEvidence`
- `documentCandidates`
- `riskHints`
- `contextBudget`

Important interpretation:

- `flowHints` are hints, not final conclusions.
- `commentEvidence` is candidate business evidence only. It must be supported by code or docs before becoming a claim.
- `documentCandidates` are keyword-recalled candidates. Claude should open original documents if snippets are ambiguous.
- `contextBudget` prevents cluster packs from growing without bound.

Route/page naming:

- `project_scanner.py` extracts route comments and route meta/title/name/label style display names.
- This helps avoid generic English page names like `User List Page` when the project has business comments/titles.
- Byte-offset handling for tree-sitter was fixed to avoid Chinese text slicing bugs.

## Claude Code Agents

Current templates:

```text
agents/claude/change-intent-judge.md
agents/claude/evidence-checker.md
agents/claude/case-writer.md
agents/claude/case-refiner.md
```

Installation:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --install-claude-agents
```

Rules:

- Ask user before installing into target `.claude/agents/`.
- Do not overwrite existing same-named agents without explicit confirmation and `--overwrite-claude-agents`.
- Installer now validates target project root exists before writing.
- After install, restart Claude Code or use `/agents` so Claude Code loads the new agents.

Agent roles:

- `change-intent-judge`: one cluster only; determine precise user-visible change, function units, evidence, confidence, uncertainties.
- `evidence-checker`: one cluster only; verify claims/cases against code, route, diff, and docs; downgrade/remove unsupported claims.
- `case-writer`: one verified cluster only; write specific QA cases with evidence.
- `case-refiner`: after merge; refine final cases without changing intent, operation flow, scope, evidence, priority, or confidence.

## Case Generation Contract

The old Python template case path is intentionally removed from the main flow.

Correct case flow:

```text
cluster-context/*.json
-> Claude writes cluster-analysis/*.analysis.json
-> Python merge produces 99-merged-result.json
-> Claude case-refiner optionally produces 99-refined-cases.json
```

Before merge:

- `cases` in `99-final-result.json` should be empty.
- `fallbackCases` should be empty.

After merge:

- `cases` come from Claude-written cluster analyses only.
- Clusters without analysis produce no cases and remain visible as `missing-analysis`.
- Validator reports generic, unsupported, unclear, or overconfident cases.

Refinement stage:

- This is not second-round generation.
- It is evidence-constrained semantic cleanup.
- It may:
  - improve wording
  - dedupe
  - reorder
  - split overlong cases
  - remove unsupported/generic cases
- It must not:
  - change case intent
  - change user operation flow
  - change expected behavior
  - add scope/pages/routes/modules
  - add unsupported expectations
  - upgrade confidence or priority
  - turn uncertainties into expected results

Refined schema:

```text
schemas/refined-cases.schema.json
```

Expected output:

```text
<runDir>/99-refined-cases.json
```

## Anthropic Skill Review Findings Already Addressed

Addressed during this iteration:

1. Relative `scripts/front_end_impact_analyzer.py` commands were not portable from target repos.
   - Fixed by requiring `<skill_root>` and `uv run --project "<skill_root>" ...`.

2. Required preflight failures did not stop analysis.
   - Fixed by blocked result/state and exit.

3. Agent installer could write into a mistyped project path.
   - Fixed by validating project root exists.

4. Installed subagents may not be loaded in current Claude Code session.
   - Docs now tell user to restart Claude Code or use `/agents`.

5. Windows/PowerShell command compatibility.
   - Docs now use one-line quoted commands instead of Bash continuations.

6. Root-level result files were overwritten.
   - Defaults now keep artifacts/results inside each run dir; root exports are opt-in.

## Tests And Current Verification

Most recent known test command:

```text
uv run pytest -q
```

Most recent result:

```text
30 passed in 0.11s
```

Tests cover:

- diff parsing
- noise classification
- project scanner route comments/meta titles
- workflow intermediates
- cluster tasks
- merger
- validator
- no-template-cases rule
- schemas including refined cases

## Current Dirty Worktree Notes

The worktree is intentionally dirty with many changes from this iteration.

Do not revert unknown changes. Some are from earlier work in the same thread.

Expected notable changes:

- `TODO.md` is deleted.
- old `.claude/agents/*.md` were moved to `agents/claude/*.md`.
- `agents/claude/case-refiner.md` is new.
- `schemas/refined-cases.schema.json` is new.
- `internal/HANDOFF.md` is this file.
- `internal/REFACTOR_PLAN.md` and `internal/REAL_RUN_REVIEW.md` were moved under `internal/`.
- `.impact-analysis/` should remain ignored.
- `.venv`, `.pytest_cache`, fixtures, tests are development artifacts and should not be part of a trimmed release package.

## Release Packaging Recommendation

Development repo can keep tests/fixtures/internal docs.

Release/installed skill should probably include:

```text
SKILL.md
pyproject.toml
uv.lock
scripts/
schemas/
references/
agents/claude/
```

Do not include in a release skill package unless intentionally needed:

```text
tests/
fixtures/
internal/
.impact-analysis/
.pytest_cache/
.venv/
__pycache__/
.git/
.DS_Store
```

## Known Limitations

Still true:

- Symbol-level tracing is only partial, strongest at first hop.
- API field-level diff analysis is heuristic, not a full contract diff.
- Document retrieval is keyword-based candidate recall.
- Dynamic route factories and generated route systems may remain unresolved.
- Comment evidence is useful but cannot be treated as proof alone.
- Large shared/global changes still need careful representative-flow analysis.
- `SKILL.md` is still relatively long; future cleanup could move more details into references for better progressive disclosure.

## Recommended Next Work

Highest-value next tasks:

1. Run on a real Windows Claude Code environment.
   - Verify `uv` command works in PowerShell.
   - Verify paths with spaces.
   - Verify agent install and `/agents` reload.

2. Do one real medium-size project run.
   - Prefer 2k-8k diff lines before trying a 50k release diff.
   - Fill `internal/REAL_RUN_REVIEW.md`.

3. Validate final output quality.
   - Check if cluster contexts contain enough evidence.
   - Check if Claude cases are still generic.
   - Check if `case-refiner` preserves intent and improves readability.

4. Improve `SKILL.md` progressive disclosure.
   - Keep trigger + core workflow in `SKILL.md`.
   - Move long examples and detailed rules into `references/`.

5. Add CLI tests for default run-dir-only output.
   - Ensure no root-level files are created unless `--state-output` or `--result-output` is provided.

6. Consider adding a release packaging script.
   - Build a clean skill package without tests, fixtures, internal docs, caches, or run artifacts.

## Current Mental Model

The route is considered correct:

```text
global scan + deterministic evidence
-> cluster-level local context
-> Claude semantic judgment per cluster
-> validator-backed merge
-> evidence-preserving final refinement
```

The main risk is not "Claude cannot analyze code." It can. The risk is feeding it the wrong granularity, weak evidence, or generic prompts. This project exists to provide the right granularity and evidence boundaries.

If future output looks generic again, debug in this order:

1. Did clustering produce meaningful clusters?
2. Did `cluster-context` include enough code, route, doc, and comment evidence?
3. Did Claude open original code/docs when snippets were insufficient?
4. Did `cluster-analysis/*.analysis.json` include concrete user-visible change and evidence?
5. Did validator flag generic/unsupported cases?
6. Did `case-refiner` preserve intent instead of inventing new scope?

