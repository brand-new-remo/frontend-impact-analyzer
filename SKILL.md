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
7. Classify non-logic noise such as format-only, comment-only, import-only, generated, lockfile, test-only, and style-only changes.
8. Scan source code, build import/reverse-import graph, bind pages and routes.
9. Build file impact seeds.
10. Group logic-like changed files into change clusters. Global/cross-cutting changes become separate global clusters instead of expanding to all pages.
11. Build `cluster-context/*.json` evidence packs.
12. Claude Code should analyze clusters one by one, using document candidates and original docs when needed.
13. Claude Code should write `cluster-analysis/*.analysis.json` for analyzed clusters.
14. Merge and validate the cluster conclusions into final QA cases and summary.

## Configuration

Command path rule:

- Let `<skill_root>` be the absolute path to this skill directory, the directory containing this `SKILL.md`.
- Claude Code is usually running inside the target business project, so do not run `scripts/front_end_impact_analyzer.py` as a project-relative path.
- Always run the bundled analyzer with `uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py"`.
- On Windows PowerShell, use the same one-line commands below and quote paths. Do not use Bash `\` line continuations; PowerShell uses backticks for line continuation, but one-line commands are preferred.
- Before the first run in a new environment, run `--doctor`. If `uv` is missing, stop and tell the user to install uv before continuing; do not guess a different command unless the user explicitly asks for a non-uv fallback.

Environment check:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --doctor
```

Default config path:

```text
impact-analyzer.config.json
```

Create it when missing:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --init-config
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
- `analysis.maxClusterContextChars`: per-cluster evidence pack size budget.

If required repo wiki is missing, tell the user to generate it with the repo-wiki skill before continuing.

## Invocation

Generate a diff from branches and analyze it:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --make-diff --base-branch "<base_branch>" --compare-branch "<compare_branch>"
```

Analyze an existing diff:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --diff-file "<diff_file>"
```

Optional arguments:

```text
--config-file <config_json>
--project-profile-file <project_profile_md>
--ignore-dir <extra_dir_to_ignore>
--analysis-output-dir <run_output_dir>
--install-claude-agents
--overwrite-claude-agents
--state-output <state_json>
--result-output <result_json>
```

`--state-output` and `--result-output` are optional extra export copies. By default, state and result files stay inside the current run artifact directory.

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
├── 98-analysis-state.json
├── 99-final-result.json
└── 99-merged-result.json
```

Primary initial result file:

```text
<runDir>/99-final-result.json
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

When the user asks for final cases, Claude Code should not stop after producing the analysis package. It should continue through the deep-analysis queue when feasible:

```text
read 06-cluster-analysis-tasks.md
-> read one cluster-context file
-> inspect source/docs when evidence snippets are insufficient
-> write cluster-analysis/<clusterId>.analysis.json
-> repeat for prioritized clusters
-> run merge
-> report merged cases and validation status
```

For each cluster with `needsDeepAnalysis=true`:

1. Read `06-cluster-analysis-tasks.md`.
2. Pick the next deep-analysis cluster.
3. Read `cluster-context/<clusterId>.json`.
4. Inspect `diffEvidence`, `codeEvidence`, and `documentCandidates`.
5. Inspect `traceEvidence`, `routeEvidence`, `flowHints`, and `riskHints` before making impact claims.
6. Inspect `commentEvidence` as candidate business evidence, not final proof.
7. If document snippets are ambiguous or insufficient, open the original repo-wiki/requirement/spec files around the matched headings or sections.
8. Use the `change-intent-judge` agent when available to determine the precise user-visible change.
9. Use the `evidence-checker` agent when available to verify claims and confidence.
10. Use the `case-writer` agent when available to write cluster-specific QA cases.
11. Keep evidence and uncertainty explicit.
12. Avoid broadening scope beyond the evidence.

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
  "cases": [
    {
      "moduleName": "orders",
      "pageName": "订单列表",
      "routePath": "/orders",
      "caseName": "批量编辑弹窗提交时传递更新后的字段值",
      "businessGoal": "验证批量编辑提交链路按本次变更传递字段并刷新列表",
      "entry": {"route": "/orders", "page": "订单列表"},
      "preconditions": ["存在可批量编辑的订单数据"],
      "testSteps": ["进入订单列表", "选择多条订单", "打开批量编辑弹窗", "修改字段并提交"],
      "expectedResults": ["提交请求包含修改后的字段值", "提交成功后弹窗关闭并刷新列表"],
      "priority": "high",
      "confidence": "high",
      "evidence": []
    }
  ]
}
```

After writing one or more cluster analysis files, merge them:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --merge-cluster-analysis --run-dir "<run_artifact_dir>"
```

Merged result behavior:

- `cases`: normalized cases from Claude-written `cluster-analysis/*.analysis.json`
- `fallbackCases`: reserved compatibility field; clusters without Claude analysis produce no cases
- `clusters`: analyzed/missing-analysis status per cluster
- `validationReports`: quality checks for missing evidence, generic wording, and unclear user actions
- `meta.analysisStatus`: `success`, `partial_success`, or `needs_cluster_analysis`

After merge, optionally use the `case-refiner` agent to write `<runDir>/99-refined-cases.json`.

Refinement is semantic cleanup based on existing code and document evidence. It must preserve each case's intent, user operation flow, expected behavior, scope, evidence, priority, and confidence. It may improve wording, dedupe, reorder, split overlong cases, or remove unsupported/generic cases. It must not add new pages, routes, expectations, business scope, or cases without existing evidence.

## Decision Rules

- Do not analyze a 50k-line diff as one prompt-sized object.
- Use `03-diff-index.json` for global overview.
- Use `05-change-clusters.json` for prioritization.
- Use `06-cluster-analysis-tasks.md` as the work queue.
- Use `cluster-context/*.json` for local reasoning.
- Initial `cases` is intentionally empty. Python does not generate template fallback cases.
- High-confidence non-logic noise stays visible in `03-diff-index.json` and `coverage.filesByNoiseKind`, but is not traced or clustered.
- Global or cross-cutting changes should be analyzed as their own cluster with representative flows; do not generate cases for every page.
- Merged `cases` should come from cluster-level Claude reasoning.
- Refined cases must keep the merged case intent and operation flow unchanged; refinement is not a second round of case generation.
- Merge validates cluster-analysis quality and reports generic or unsupported cases.
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
- route comments and route meta/title display-name extraction
- business-code comment evidence collection near changed hunks, changed symbols, and business keywords
- symbol-level first-hop filtering
- format-only diff skipping
- API field-level diff heuristics
- diff indexing
- non-logic diff noise classification
- global/cross-cutting change classification without all-page expansion
- file impact seeds
- page/module-based change clustering
- per-cluster code/document evidence packs
- explicit trace evidence, route evidence, risk hints, and context budget metadata
- flow hints for entry route, user action, and state-change reasoning
- cluster-analysis validation reports during merge
- cluster analysis task markdown generation
- coverage reporting

## Claude Code Agents

This skill includes optional Claude Code subagent templates:

- `agents/claude/change-intent-judge.md`
- `agents/claude/evidence-checker.md`
- `agents/claude/case-writer.md`
- `agents/claude/case-refiner.md`

These are templates bundled with the skill. They are not loaded from the skill directory when Claude Code is running inside the target business project. To enable them, ask the user for confirmation, then install them into the target project's `.claude/agents/` directory:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --install-claude-agents
```

After installing agent files manually or through this command, restart the Claude Code session or use `/agents` so Claude Code loads the new project subagents before the cluster-analysis step.

If the target project already has same-named agents, the installer skips them by default. Only overwrite after explicit user confirmation:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --install-claude-agents --overwrite-claude-agents
```

Use the installed agents per cluster, not for the whole diff. The main Claude Code thread should keep orchestration ownership: choose clusters, call or follow agent instructions, write `cluster-analysis/*.analysis.json`, run merge, then use `case-refiner` only for final evidence-preserving wording and dedupe.

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
- Real project validation workflow: `references/real-run-workflow.md`
- Internal refactor plan: `internal/REFACTOR_PLAN.md`
- Real run review template: `internal/REAL_RUN_REVIEW.md`
