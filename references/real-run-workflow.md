# Real Run Workflow

Use this guide when validating the skill on a real project diff. The goal is not to prove every case is perfect on the first run. The goal is to learn whether clustering, evidence packs, Claude cluster analysis, and validation are good enough for real QA work.

## Recommended Sample

Pick a medium-complexity change first:

- 2k to 8k diff lines.
- 3 to 8 functional changes.
- At least one page or route change.
- At least one component, hook, API, or shared-component change.
- Requirements/specs/repo-wiki available if the real workflow expects them.

Avoid starting with a tiny fixture or a 50k-line release diff. Tiny samples hide workflow problems; huge samples make diagnosis slow.

## Run The Analyzer

Set `<skill_root>` to the absolute path of the frontend-impact-analyzer skill directory. Run the bundled script through that path even when Claude Code is currently inside the target business project.

Use one-line commands with quoted paths. This is compatible with PowerShell and Bash. Do not copy Bash `\` line continuations into PowerShell.

Check the environment first. If `uv` is missing, stop and ask the user to install uv before continuing:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --doctor
```

Create config if needed:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --init-config
```

Optionally install Claude Code subagent templates into the target project after user confirmation:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --install-claude-agents
```

If same-named agents already exist, the installer skips them. Use overwrite only after explicit confirmation:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --install-claude-agents --overwrite-claude-agents
```

Generate and analyze branch diff:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --make-diff --base-branch "<base_branch>" --compare-branch "<compare_branch>" --ignore-dir "<extra_ignored_dir_if_needed>"
```

Or analyze an existing diff:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --diff-file "<diff_file>"
```

Record the run artifact directory from CLI output. It should contain:

```text
00-run-manifest.json
01-preflight-report.json
03-diff-index.json
05-change-clusters.json
06-cluster-analysis-tasks.md
cluster-context/*.json
cluster-analysis/
90-coverage-report.json
98-analysis-state.json
99-final-result.json
```

The default workflow does not write root-level result files. Use `--state-output` or `--result-output` only when an extra export copy is needed.

## Inspect Before Writing Cases

Check these files first:

- `01-preflight-report.json`: missing repo-wiki/spec/requirements?
- `03-diff-index.json`: expected changed files? ignored files reasonable?
- `03-diff-index.json`: are non-logic noise classifications correct?
- `05-change-clusters.json`: are clusters coherent and small enough?
- `06-cluster-analysis-tasks.md`: are the highest-value clusters obvious?
- `cluster-context/<clusterId>.json`: does each selected cluster include useful evidence?

For each selected cluster, inspect:

- `diffEvidence`: are hunks relevant?
- `traceEvidence`: does it explain how changed files reach pages?
- `routeEvidence`: does it give a route/page entry?
- `routeEvidence`: does it include useful display names from route comments or meta titles?
- `flowHints`: does it help infer user actions and state changes?
- `codeEvidence`: enough local code to understand the change?
- `commentEvidence`: are nearby business comments useful and not treated as final proof?
- `documentCandidates`: relevant requirement/spec/wiki sections?
- `riskHints`: useful warnings without becoming fake conclusions?
- `contextBudget`: was the context truncated?

Noise review:

- Were format-only/comment-only/import-only changes excluded from clusters?
- Were generated files and lockfiles excluded from clusters?
- Were any real product changes incorrectly marked as noise?
- Were any noisy files incorrectly sent to deep analysis?

## Analyze A Small Set First

Do not analyze every cluster on the first validation pass. Pick:

- one direct page/route cluster
- one business component or hook cluster
- one shared component or API cluster

For each, write:

```text
cluster-analysis/<clusterId>.analysis.json
```

The cluster analysis should:

- identify the precise user-visible change
- cite code evidence and document evidence
- include uncertainties when behavior is not proven
- generate only evidence-backed cases
- avoid generic smoke cases
- include clear user actions and expected results

## Merge And Validate

Run:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --merge-cluster-analysis --run-dir "<run_artifact_dir>"
```

Review:

- `cases`
- `clusters[].validationStatus`
- `validationReports`
- `summary.validationIssueCount`
- `summary.validationWarningCount`

Fix cluster-analysis files when validator reports:

- missing evidence
- unclear user action
- generic template-like wording
- high confidence without code evidence

## Refine Final Cases

After merge, optionally use the installed `case-refiner` agent to create:

```text
<runDir>/99-refined-cases.json
```

The refiner must optimize wording according to code and document evidence without changing case intent or operation flow. It may dedupe, reorder, split overlong cases, or remove unsupported/generic cases. It must not add scope, pages, routes, expectations, cases, or upgrade confidence.

## Decision Rules

- If clusters are too large, improve clustering before tuning prompts.
- If global/cross-cutting changes expand to every page, fix global clustering before writing more cases.
- If clusters are good but context is weak, improve evidence packs.
- If comments are useful but missing, improve commentEvidence extraction before prompt tuning.
- If context is good but cases are generic, improve Claude instructions, agents, schema examples, or validator rules.
- If validator catches too much, tune it using real false positives.
- If validator catches too little, add rules based on observed bad outputs.
