# Agent Usage Notes

## Goal

This skill is designed for Claude Code / Codex style agent-to-tool usage.

The analyzer now produces an analysis package plus run artifacts:

- `<runDir>/99-final-result.json`: summary, coverage, clusters, empty initial cases, next steps
- `<runDir>/99-merged-result.json`: final merged result after Claude cluster analyses
- `<runDir>/05-change-clusters.json`: cluster overview
- `<runDir>/06-cluster-analysis-tasks.md`: cluster work queue for Claude Code
- `<runDir>/cluster-context/*.json`: focused evidence packs for cluster-level reasoning
- `<runDir>/98-analysis-state.json`: state snapshot used by merge for route display names and graph evidence

## Recommended Agent Pattern

1. Run `--doctor` to check environment, including potential venv conflicts.
2. Check whether `impact-analyzer.config.json` exists.
3. If it does not exist, create it with `--init-config`. The output will include `"userActionRequired": true`. **STOP here.** Show the user the config file path and key sections (`diff.ignoreDirs`, `diff.ignoreFiles`, `diff.ignoreGlobs`, `paths.*`, `analysis.requireRepoWiki`). Ask the user to review and confirm. **Do NOT proceed to any later step until the user explicitly says the config is ready.** If the user wants to modify it, wait until they finish and tell you to continue.
4. If it already exists, do not overwrite or regenerate it. Load and use it directly.
5. Run or inspect preflight through a normal analysis run.
6. Ask whether to install the bundled Claude Code subagent templates into the target project's `.claude/agents/` directory.
7. If the user confirms, run `--install-claude-agents`; only use `--overwrite-claude-agents` after explicit confirmation. After installing, tell the user to restart the Claude Code session or use `/agents` so the new subagents are loaded.
8. If required repo wiki / requirements / specs are missing, stop and ask the user to generate or provide them.
9. Ask which base branch and compare branch to diff, unless the user already provided them.
10. Ask whether configured diff ignores are acceptable and whether extra ignored folders are needed.
11. Generate the diff with `--make-diff`. This **only generates the diff file and stops** — it does not start analysis. Always use `--make-diff` instead of manual `git diff` — only `--make-diff` applies the configured ignore rules from `impact-analyzer.config.json`.
12. Show the user the generated diff path and size stats. Ask whether the diff size is acceptable. If too large, suggest adjusting ignore rules in the config.
13. Once the user confirms, run analysis with `--diff-file "<generated_diff_path>"`. If the diff exceeds `analysis.phasedExecutionThreshold` (default 1000 lines), the analyzer **automatically** runs only the parse phase and prints the run dir and the exact next command. Follow the printed instructions to run each subsequent phase:
    - `--phase scan --run-dir "<run_dir>"` → writes `phase-02-scan.json`
    - `--phase impact --run-dir "<run_dir>"` → writes `phase-03-impact.json`
    - `--phase cluster --run-dir "<run_dir>"` → writes all final artifacts
    Each phase prints the next command. Run them in order until `phase:cluster` completes. `--phase analyze` is a shortcut that runs impact + cluster in one invocation.
14. Read `<runDir>/99-final-result.json`.
15. Read the run artifact directory from CLI output or `00-run-manifest.json`.
16. Read `06-cluster-analysis-tasks.md`.
17. For large diffs, use clusters as the primary workflow.
18. Analyze prioritized clusters one at a time and write `cluster-analysis/*.analysis.json`.
19. After writing cluster-analysis files, run merge and use the merged `cases` as the final cases.
20. Read `validationReports` and fix generic or unsupported cases when needed.

## Cluster Workflow

For each cluster with `needsDeepAnalysis=true`:

1. Read `06-cluster-analysis-tasks.md`.
2. Read `cluster-context/<clusterId>.json`.
3. Inspect `diffEvidence`, `traceEvidence`, `routeEvidence`, `flowHints`, `codeEvidence`, `commentEvidence`, `riskHints`, and `documentCandidates`.
4. Open original repo-wiki / requirement / spec files when snippets or matched headings are not enough.
5. Use the installed `.claude/agents/change-intent-judge.md` when available to determine the precise user-visible change.
6. Use the installed `.claude/agents/evidence-checker.md` when available to verify claims.
7. Use the installed `.claude/agents/case-writer.md` when available to write cases.
8. Write uncertainty when evidence is weak.

Recommended output file:

```text
cluster-analysis/<clusterId>.analysis.json
```

Merge command:

```text
uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --merge-cluster-analysis --run-dir "<run_artifact_dir>"
```

Merged output rules:

- `cases` contains Claude cluster-analysis cases.
- `fallbackCases` is a reserved compatibility field and should normally be empty.
- Clusters without analysis produce no cases.
- `validationReports` highlights generic language, missing evidence, and unclear user actions.

After merge, use `case-refiner` when available to create `<runDir>/99-refined-cases.json`.

Refinement rules:

- Refine according to existing code evidence, document evidence, and validation reports.
- Preserve every case's original intent, user operation flow, expected behavior, evidence, priority, and confidence.
- Improve wording, dedupe, reorder, split overlong cases, or remove unsupported/generic cases.
- Do not add new business scope, impacted pages, routes, expected results, or cases.
- Output must match `schemas/refined-cases.schema.json`.

Before merge:

- Initial `cases` is intentionally empty.
- Initial `fallbackCases` is intentionally empty.

## If Status Is `success`

- Use the analysis package.
- Even for small diffs, final cases should come from cluster analysis.
- For large diffs, continue with cluster-level analysis.

## If Status Is `partial_success`

- Use the analysis package cautiously.
- Surface:
  - `codeImpact.unresolvedFiles`
  - `codeGraph.diagnostics`
  - `codeImpact.sharedRisks`
  - `coverage.warnings`

## If Status Is `failed`

- Do not invent fallback output.
- Read the fatal diagnostic from `codeGraph.diagnostics`.

## Output Discipline

- Do not reclassify formatting-only changes as real impact.
- Do not expand shared-component changes to unrelated pages.
- Do not expand global/cross-cutting changes to every page. Use the global cluster to choose representative affected flows.
- Do not add unsupported pages or routes.
- Prefer routeEvidence display names from route comments/meta titles over English file-derived page names.
- Treat `commentEvidence` as candidate evidence. Use it with code or document support, and record uncertainty if comments may be stale.
- Do not invent requirement/spec behavior that is not in document evidence.
- Do not generate Python template fallback cases.
- After merge, use `cases`; inspect missing-analysis clusters for unfinished work.
- Do not execute test cases.
- Do not hard-code one target project's folder structure or naming rules into this skill.

## Good Downstream Usage

- Use `03-diff-index.json` for global triage.
- Check `noiseClassification` and `coverage.filesByNoiseKind` to understand which files were excluded from deep analysis as non-logic noise.
- Use `05-change-clusters.json` to choose analysis order.
- Use `06-cluster-analysis-tasks.md` as the actionable work queue.
- Use `cluster-context/*.json` as compact evidence packs for Claude/subagents.
- Check `contextBudget` to see whether snippets were truncated.
- Use `90-coverage-report.json` to explain what was deeply analyzed, shallowly analyzed, or skipped.
- For real project validation, follow `references/real-run-workflow.md` and fill `internal/REAL_RUN_REVIEW.md`.
