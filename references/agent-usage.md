# Agent Usage Notes

## Goal

This skill is designed for Claude Code / Codex style agent-to-tool usage.

The analyzer now produces an analysis package plus run artifacts:

- `impact-analysis-result.json`: summary, coverage, clusters, empty initial cases, next steps
- `impact-analysis-merged-result.json`: final merged result after Claude cluster analyses
- `impact-analysis-state.json`: full state and graph evidence
- `<runDir>/05-change-clusters.json`: cluster overview
- `<runDir>/06-cluster-analysis-tasks.md`: cluster work queue for Claude Code
- `<runDir>/cluster-context/*.json`: focused evidence packs for cluster-level reasoning

## Recommended Agent Pattern

1. Check whether `impact-analyzer.config.json` exists.
2. If it does not exist, create it with `--init-config` or ask the user before creating it.
3. Run or inspect preflight through a normal analysis run.
4. If required repo wiki / requirements / specs are missing, stop and ask the user to generate or provide them.
5. Ask which base branch and compare branch to diff, unless the user already provided them.
6. Ask whether configured diff ignores are acceptable and whether extra ignored folders are needed.
7. Generate the diff with `--make-diff`, or use the provided diff file.
8. Run the analyzer.
9. Read `impact-analysis-result.json`.
10. Read the run artifact directory from CLI output or `00-run-manifest.json`.
11. Read `06-cluster-analysis-tasks.md`.
12. For large diffs, use clusters as the primary workflow.
13. After writing cluster-analysis files, run merge and use the merged `cases` as the final cases.

## Cluster Workflow

For each cluster with `needsDeepAnalysis=true`:

1. Read `06-cluster-analysis-tasks.md`.
2. Read `cluster-context/<clusterId>.json`.
3. Inspect `diffEvidence`, `codeEvidence`, and `documentCandidates`.
4. Open original repo-wiki / requirement / spec files when snippets are not enough.
5. Use `.claude/agents/change-intent-judge.md` when available to determine the precise user-visible change.
6. Use `.claude/agents/evidence-checker.md` when available to verify claims.
7. Use `.claude/agents/case-writer.md` when available to write cases.
8. Write uncertainty when evidence is weak.

Recommended output file:

```text
cluster-analysis/<clusterId>.analysis.json
```

Merge command:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --merge-cluster-analysis \
  --run-dir <run_artifact_dir> \
  --result-output impact-analysis-merged-result.json
```

Merged output rules:

- `cases` contains Claude cluster-analysis cases.
- `fallbackCases` is a reserved compatibility field and should normally be empty.
- Clusters without analysis produce no cases.

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
- Do not add unsupported pages or routes.
- Do not invent requirement/spec behavior that is not in document evidence.
- Do not generate Python template fallback cases.
- After merge, use `cases`; inspect missing-analysis clusters for unfinished work.
- Do not execute test cases.
- Do not hard-code one target project's folder structure or naming rules into this skill.

## Good Downstream Usage

- Use `03-diff-index.json` for global triage.
- Use `05-change-clusters.json` to choose analysis order.
- Use `06-cluster-analysis-tasks.md` as the actionable work queue.
- Use `cluster-context/*.json` as compact evidence packs for Claude/subagents.
- Use `90-coverage-report.json` to explain what was deeply analyzed, shallowly analyzed, or skipped.
