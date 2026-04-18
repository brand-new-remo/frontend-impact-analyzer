---
name: frontend-impact-analyzer
description: run a full front-end change-impact workflow for React/React Router/Vite projects, including preflight checks, branch diff generation, large-diff indexing, page/route tracing, change clustering, per-cluster evidence packs, document retrieval from repo-wiki/requirements/specs, and an evidence-backed QA analysis package.
---

# Frontend Impact Analyzer

Use this skill to turn a front-end branch diff into evidence-backed QA impact analysis.

The skill is designed for large PRs and release diffs. It should not ask the user to manually prepare every input first. It should check context, generate a diff when needed, create intermediate evidence files, and guide Claude Code through per-cluster analysis instead of treating the whole diff as one blob.

## Core Workflow

1. Load or create `impact-analyzer.config.json`.
2. Run preflight checks for repo wiki, requirements, specs, git state, and output paths.
3. Ask the user for base branch and compare branch if they were not provided.
4. Ask whether to use configured diff ignores and whether to add extra ignored folders.
5. Generate a named diff file when `--make-diff` is used.
6. Parse and index the diff.
7. Scan source code, build import/reverse-import graph, bind pages and routes.
8. Build file impact seeds.
9. Group changed files into change clusters.
10. Build `cluster-context/*.json` evidence packs.
11. Let Claude Code analyze clusters one by one, using document candidates and original docs when needed.
12. Merge the cluster conclusions into final QA cases and summary.

## Configuration

Default config path:

```text
impact-analyzer.config.json
```

Create it when missing:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --init-config
```

Important config sections:

- `paths.repoWikiDir`: repo-wiki output directory.
- `paths.projectProfileFile`: project analysis / project profile document.
- `paths.requirementsDir`: requirement documents directory.
- `paths.specsDir`: developer spec documents directory.
- `paths.diffDir`: generated diff output directory.
- `paths.outputDir`: run artifact output directory.
- `diff.ignoreDirs`, `diff.ignoreFiles`, `diff.ignoreGlobs`: paths excluded from generated git diff.
- `analysis.requireRepoWiki`, `analysis.requireRequirements`, `analysis.requireSpecs`: whether missing context should block or warn.

If required repo wiki is missing, tell the user to generate it with the repo-wiki skill before continuing.

## Invocation

Generate a diff from branches and analyze it:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --make-diff \
  --base-branch <base_branch> \
  --compare-branch <compare_branch>
```

Analyze an existing diff:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --diff-file <diff_file>
```

Optional arguments:

```bash
--config-file <config_json>
--project-profile-file <project_profile_md>
--ignore-dir <extra_dir_to_ignore>
--analysis-output-dir <run_output_dir>
--state-output <state_json>
--result-output <result_json>
```

Generated diff names follow:

```text
diff_<base>_to_<compare>_<YYYYMMDD_HHMMSS>.patch
```

Branch names are sanitized for filenames, while the run manifest keeps the real branch names.

## Run Artifacts

Each run writes an artifact directory under the configured output directory:

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
│   ├── cluster-001.json
│   └── cluster-002.json
├── cluster-analysis/
├── 90-coverage-report.json
├── 99-final-result.json
└── 99-merged-result.json
```

Primary result file:

```text
impact-analysis-result.json
```

The first result is an analysis package, not a bare case array:

- `meta`
- `summary`
- `coverage`
- `clusters`
- `cases`: empty before merge; populated only by merged Claude cluster analyses
- `fallbackCases`: reserved compatibility field; should normally remain empty
- `nextStepsForClaude`

Schema:

```text
schemas/analysis-result.schema.json
```

## Claude Code Cluster Analysis

Do not produce generic fallback cases. For large or important diffs, use the clusters.

For each cluster with `needsDeepAnalysis=true`:

1. Read `06-cluster-analysis-tasks.md`.
2. Pick the next deep-analysis cluster.
3. Read `cluster-context/<clusterId>.json`.
4. Inspect `diffEvidence`, `codeEvidence`, and `documentCandidates`.
5. If document snippets are ambiguous or insufficient, open the original repo-wiki/requirement/spec files around the matched sections.
6. Use the `change-intent-judge` agent when available to determine the precise user-visible change.
7. Use the `evidence-checker` agent when available to verify claims and confidence.
8. Use the `case-writer` agent when available to write cluster-specific QA cases.
9. Keep evidence and uncertainty explicit.
10. Avoid broadening scope beyond the evidence.

Recommended cluster-analysis output shape:

```json
{
  "clusterId": "cluster-001",
  "changeIntent": "modal-submit-flow",
  "userVisibleChange": "订单列表批量编辑弹窗的提交链路发生变化",
  "affectedFunctionUnits": [
    "批量编辑入口",
    "弹窗打开关闭",
    "表单字段校验",
    "提交请求参数",
    "提交后列表刷新"
  ],
  "codeEvidenceUsed": [],
  "docEvidenceUsed": [],
  "confidence": "high",
  "uncertainties": [],
  "cases": []
}
```

After writing one or more cluster analysis files, merge them:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --merge-cluster-analysis \
  --run-dir <run_artifact_dir> \
  --result-output impact-analysis-merged-result.json
```

Merged result behavior:

- `cases`: normalized cases from Claude-written `cluster-analysis/*.analysis.json`
- `fallbackCases`: reserved compatibility field; clusters without Claude analysis produce no cases
- `clusters`: analyzed/missing-analysis status per cluster
- `meta.analysisStatus`: `success`, `partial_success`, or `needs_cluster_analysis`

## Decision Rules

- Do not analyze a 50k-line diff as one prompt-sized object.
- Use `03-diff-index.json` for global overview.
- Use `05-change-clusters.json` for prioritization.
- Use `06-cluster-analysis-tasks.md` as the work queue.
- Use `cluster-context/*.json` for local reasoning.
- Initial `cases` is intentionally empty. Python does not generate template fallback cases.
- Merged `cases` should come from cluster-level Claude reasoning.
- Do not invent pages or routes that are not supported by trace evidence.
- Do not invent requirements that are not supported by requirement/spec/wiki evidence.
- If evidence is weak, keep confidence low and write an uncertainty.
- If a shared component changes, do not expand to the whole system unless traces support the affected pages.
- Formatting-only changes may produce no cases.

## Current Analyzer Capabilities

- tsconfig alias resolution, including `extends`
- multi-target aliases
- barrel exports and multi-hop re-export traversal
- nested routes and lazy routes
- symbol-level first-hop filtering
- format-only diff skipping
- API field-level diff heuristics
- diff indexing
- file impact seeds
- page/module-based change clustering
- per-cluster code/document evidence packs
- cluster analysis task markdown generation
- coverage reporting

## Claude Code Agents

This skill includes optional project-level Claude Code agents:

- `.claude/agents/change-intent-judge.md`
- `.claude/agents/evidence-checker.md`
- `.claude/agents/case-writer.md`

Use them per cluster, not for the whole diff. The main Claude Code thread should keep orchestration ownership: choose clusters, call or follow agent instructions, write `cluster-analysis/*.analysis.json`, then run merge.

## Known Limits

- Cluster intent is not fully inferred by Python; Claude Code should perform cluster-level semantic judgment.
- Document retrieval is keyword-based candidate recall, not final semantic proof.
- API field analysis is heuristic, not a full contract diff.
- Symbol tracing is strongest at the first hop.
- Dynamic route factories and generated route systems may remain unresolved.

## Response Behavior

After running this skill:

- Report the run artifact directory.
- Report `meta.analysisStatus`.
- Summarize coverage: changed files, cluster count, deep-analysis clusters, diagnostics.
- For large diffs, tell the user which clusters should be analyzed first.
- Surface missing repo wiki/spec/requirements from `01-preflight-report.json`.
- Before merge, `cases` should be empty.
- After merge, use merged `cases`; clusters without Claude analysis must remain case-less and visible as `missing-analysis`.

## Resources

- Project conventions and extension ideas: `references/project-conventions.md`
- Impact and confidence rules: `references/impact-rules.md`
- Route tracing notes: `references/route-conventions.md`
- Agent usage notes: `references/agent-usage.md`
