# Frontend Impact Analyzer Refactor Plan

This plan captures the current direction so future Codex/Claude sessions can continue after context compaction.

## Core Decision

Python should not be the business analyst.

The project should move from:

```text
Python analyzes diff and generates QA cases
```

to:

```text
Python collects evidence, indexes large diffs, builds clusters, packages context, and merges Claude-written cluster analyses.
Claude Code reads each cluster context, understands the business change, and writes precise QA cases.
```

Guiding rule:

```text
If logic is about understanding business change, give it to Claude.
If logic is about deterministic evidence collection, indexing, splitting, packaging, validation, or merging, keep it in Python.
```

## Current State

Already implemented:

- Config/preflight/diff/run artifact workflow.
- Large diff indexing.
- Non-logic noise classification for format-only/comment-only/import-only/generated/lockfile/test/style changes.
- Global/cross-cutting change classification that prevents all-page expansion.
- Route comment and meta/title extraction for business display names.
- Business-code comment evidence extraction as candidate evidence.
- Structured diff hunks.
- Candidate page/route tracing.
- Change clusters.
- Cluster context evidence packs.
- `whyIncluded` on code evidence.
- Document candidate retrieval.
- `06-cluster-analysis-tasks.md`.
- Claude Code agent templates:
  - `agents/claude/change-intent-judge.md`
  - `agents/claude/evidence-checker.md`
  - `agents/claude/case-writer.md`
- `cluster-analysis/*.analysis.json` contract.
- Merge mode:
  - `--merge-cluster-analysis`
  - `--run-dir`
- Initial output now has:
  - `cases: []`
  - `fallbackCases: []`
  - missing clusters marked through `missingAnalysisClusterCount`
- Merge output only puts Claude-written cluster-analysis cases into `cases`.
- Missing cluster analysis produces no cases.

Current verification:

```text
uv run pytest -q
20 passed
```

Important current generated sample files are ignored under `.impact-analysis/`.

## Main Problem Being Solved

Old Python-generated cases were generic template output, for example:

```text
User List Page 页面基础回归
User List Page 表单展示校验与提交流程验证
```

These do not help QA understand the actual change. The system must not present such template cases as real output.

Current desired behavior:

- No Claude cluster-analysis means no cases.
- Claude cluster-analysis is required for precise cases.
- Python only provides evidence and workflow scaffolding.

## Target Architecture

Recommended final module shape:

```text
scripts/
  front_end_impact_analyzer.py
  analyzer/
    __init__.py
    run_workflow.py
    models.py
    common.py
    diff_indexer.py
    source_classifier.py
    ast_facts.py
    graph_scanner.py
    candidate_tracer.py
    cluster_builder.py
    evidence_packager.py
    cluster_tasks.py
    result_merger.py
    deprecated/
      case_builder.py
```

Do not rename everything at once. Prefer staged migration.

## Phase 1: Semantic Slimming

Goal: make output language honest without large file renames.

Tasks:

- Keep `case_builder.py` out of the main flow.
- Mark `case_builder.py` as deprecated or move it later.
- Ensure no Python-generated template cases appear in initial or merged output.
- Rename conceptual output:
  - `businessImpact` -> `candidateImpact`
  - `affectedFunctions` -> `structuralHints`
  - `pageImpacts` -> `candidatePageTraces`
- If old fields are kept for compatibility, place them under `deprecated` or clearly mark them deprecated.
- Update `SKILL.md`, `references/agent-usage.md`, and schemas to reflect:
  - Python never generates final cases.
  - Cases come only from `cluster-analysis`.

Status:

- No template cases in output: done.
- Field rename/deprecation: mostly done.
  - `candidateImpact` added to state.
  - Result summary now uses `candidateModules`, `candidatePages`, and `structuralHints`.
  - `codeImpact.candidatePageTraces` added.
  - Old `businessImpact` and `codeImpact.pageImpacts` remain as deprecated compatibility fields.
  - `statusSummary.pageImpactCount` remains for compatibility; prefer `candidatePageTraceCount`.
  - Cluster summaries include `contextFile` and `analysisOutputFile`.
- Schema cleanup: done.
  - `analysis-result.schema.json` supports both initial analysis packages and merged cluster-analysis results.
  - `analysis-state.schema.json` explicitly models `candidateImpact`, workflow artifacts, and deprecated compatibility fields.

## Phase 2: Output Contract Cleanup

Goal: JSON should no longer imply Python has made business conclusions.

Initial result should look like:

```json
{
  "meta": {
    "status": "needs_cluster_analysis"
  },
  "summary": {
    "changedFileCount": 50,
    "clusterCount": 8,
    "missingAnalysisClusterCount": 8,
    "caseCount": 0
  },
  "coverage": {},
  "clusters": [
    {
      "clusterId": "cluster-001",
      "title": "...",
      "candidatePages": [],
      "candidateRoutes": [],
      "changedFiles": [],
      "contextFile": "cluster-context/cluster-001.json",
      "analysisOutputFile": "cluster-analysis/cluster-001.analysis.json"
    }
  ],
  "cases": []
}
```

Merge result should look like:

```json
{
  "meta": {
    "status": "success"
  },
  "summary": {
    "clusterCount": 8,
    "analyzedClusterCount": 8,
    "caseCount": 32
  },
  "clusters": [],
  "cases": [
    {
      "clusterId": "cluster-001",
      "caseSource": "cluster-analysis",
      "caseName": "...",
      "evidence": [],
      "uncertainties": []
    }
  ]
}
```

Tasks:

- Add `candidateImpact` section to state. Done.
- Replace user-facing `affectedFunctions` with `structuralHints`. Done.
- Add `contextFile` and `analysisOutputFile` to cluster summaries. Done.
- Consider removing `fallbackCases` from required schema, or keep it as an always-empty compatibility field. Kept as empty compatibility field.
- Update snapshot tests.

## Phase 3: Module Role Renaming

Goal: code names should match the new responsibility boundaries.

Recommended renames:

- `impact_engine.py` -> `candidate_tracer.py`
- `ImpactAnalyzer` -> `CandidateTracer`
- `PageImpact` -> `CandidatePageTrace`
- `ast_analyzer.py` -> `ast_facts.py` or keep but clarify it extracts facts only
- `ProjectScanner` -> `GraphScanner` or keep but clarify candidate scanner role
- `context_collector.py` -> `evidence_packager.py`

Rules:

- Do this after output semantics are cleaned.
- Update tests in the same PR/change.
- Avoid changing behavior while renaming if possible.

## Phase 4: Deprecate Old Case Builder

Goal: remove tests and docs that reinforce generic template cases.

Tasks:

- Move `scripts/analyzer/case_builder.py` to:

```text
scripts/analyzer/deprecated/case_builder.py
```

or add a top-level comment:

```python
# Deprecated: template case generation is not part of the main workflow.
```

- Delete or rewrite `tests/test_case_builder.py`.
- Remove `fixtures/expected/shared_search_form_cases.json` if no longer used.
- Keep `fixtures/expected/sample_cluster_analysis.json`.
- Keep `fixtures/expected/sample_merged_result.json`.

Status:

- `case_builder.py` kept in place with a deprecation header for low-risk compatibility.
- `tests/test_case_builder.py` removed.
- `tests/test_no_template_cases.py` added to verify the main flow skips template generation.
- `fixtures/expected/shared_search_form_cases.json` removed.

## Phase 5: Stronger Evidence Packs

Goal: improve Claude's per-cluster context quality.

Tasks:

- Preserve hunk line numbers already added.
- Add `whyIncluded` already added.
- Add `traceEvidence` into cluster context explicitly.
- Add `routeEvidence` into cluster context explicitly.
- Add document candidate headings and matched section labels.
- Add file-level `riskHints`, not final impact conclusions.
- Add per-cluster token/size budgets in config.

Status:

- Hunk line numbers and `whyIncluded`: done.
- `traceEvidence`, `routeEvidence`, and `riskHints`: done.
- `flowHints` for entry route, user actions, and state changes: done.
- Document candidate `matchedHeadings` and snippet `heading`: done.
- `analysis.maxClusterContextChars` and `contextBudget`: done.

## Phase 6: Cluster Analysis Automation and Validation

Goal: make Claude Code continue from evidence package to real cluster-level cases, while catching generic output.

Tasks:

- Strengthen `SKILL.md` so Claude Code does not stop at the analysis package when final cases are requested.
- Make `06-cluster-analysis-tasks.md` tell Claude to inspect `flowHints`, source files, and original documents.
- Add a validator for `cluster-analysis/*.analysis.json`.
- Merge validation reports into the final result.
- Normalize optional case fields such as `businessGoal` and `entry`.

Status:

- Active cluster workflow instructions: done.
- `flowHints` in `cluster-context/*.json`: done.
- `ClusterAnalysisValidator`: done.
- Merge-level `validationReports`: done.
- Schema support for `businessGoal`, `entry`, and `validationReports`: done.

## Phase 7: Better Clustering

Goal: make clusters smaller and more coherent before Claude sees them.

Possible improvements:

- Split shared component impacts by candidate page when useful.
- Group API files with callers by trace evidence.
- Use document candidate overlap as a clustering hint.
- Group route changes with related page/component changes.
- Add cluster priority based on:
  - route/page direct change
  - API contract hint
  - permission/auth hint
  - submit/save/delete hint
  - requirement/spec match

Do not implement these before Phase 1/2 cleanup unless necessary.

## Phase 8: Large Diff Noise Reduction

Goal: reduce 50k-line diff noise before tracing and clustering.

Status:

- Added `noise_classifier.py`.
- Added `ChangedFile.noise_classification`.
- `03-diff-index.json` now includes `noiseClassification`.
- Coverage now includes `filesByNoiseKind` and `noiseFileCount`.
- High-confidence non-logic noise is indexed but not traced or clustered.
- Tests cover format-only, comment-only, import-only, test-only, generated-file, and lockfile noise.

## Phase 9: Global Change Containment

Goal: keep global/cross-cutting changes visible without exploding into all-page cases.

Status:

- Added `global_change_classifier.py`.
- Added `ChangedFile.global_classification`.
- Global files are grouped into `scope: global` clusters.
- Main tracing skips global files so they do not expand to every page.
- Cluster contexts include `global-change` risk hints.
- Tests cover root `src/App.tsx` global clustering without page expansion.

## Phase 10: Business Display Names From Routes

Goal: use existing route comments and route meta/title fields as business-facing page names.

Status:

- Added `RouteInfo.route_comment`, `display_name`, and `display_name_source`.
- Route scanner extracts nearby `//` comments and `meta.title` / `handle.title` / `name` / `title`.
- Route extraction now slices tree-sitter nodes by bytes, so Chinese comments/titles do not break parsing.
- `routeEvidence` includes `routeComment`, `displayName`, and `displayNameSource`.
- Run artifacts include `98-analysis-state.json` for merge-time route display names.
- Merge falls back to route display name when a case omits `pageName`.
- Tests cover Chinese route comments and `meta.title`.

## Phase 11: Business Comment Evidence

Goal: surface useful business comments without treating them as final truth.

Status:

- Added cluster-level `commentEvidence`.
- Comments are collected from cluster code files near changed hunks, changed symbols, or business keywords.
- Each comment includes line, text, reason, and usage guidance.
- `analysisPrompt` tells Claude to treat comments as candidate evidence only.
- `analysis.maxCommentEvidencePerCluster` controls the context budget.
- Fixed `ast_analyzer.py` byte slicing so Chinese comments do not break AST extraction.
- Tests cover comment evidence near changed hunks.

## Current Files Added/Changed Recently

Important new files:

- `internal/REAL_RUN_REVIEW.md`
- `scripts/analyzer/workflow.py`
- `scripts/analyzer/cluster_builder.py`
- `scripts/analyzer/context_collector.py`
- `scripts/analyzer/cluster_tasks.py`
- `scripts/analyzer/result_merger.py`
- `schemas/analysis-result.schema.json`
- `schemas/cluster-analysis.schema.json`
- `fixtures/expected/sample_cluster_analysis.json`
- `fixtures/expected/sample_merged_result.json`
- `agents/claude/change-intent-judge.md`
- `agents/claude/evidence-checker.md`
- `agents/claude/case-writer.md`
- `references/real-run-workflow.md`

Important modified files:

- `scripts/front_end_impact_analyzer.py`
- `scripts/analyzer/models.py`
- `schemas/analysis-state.schema.json`
- `SKILL.md`
- `references/agent-usage.md`
- `tests/test_integration_output.py`
- `tests/test_workflow_intermediates.py`
- `.gitignore`

Known unrelated pre-existing dirty files:

- `code.zip` deleted
- `uv.lock` modified

Do not revert these unless the user explicitly asks.

## Next Recommended Step

Phase 1/2 cleanup, Phase 4 deprecation, Phase 5 evidence packs, and Phase 6 validation are complete. Current next step:

1. Follow `references/real-run-workflow.md` on a real or larger fixture diff.
2. Fill `internal/REAL_RUN_REVIEW.md`.
3. Review whether `flowHints` are specific enough for Claude to write precise cases.
4. Add stronger validator rules only after seeing real Claude outputs.
5. Consider module role renaming after behavior stabilizes.
6. Run:

```bash
uv run pytest -q
```

After real-output validation, consider module role renaming.
