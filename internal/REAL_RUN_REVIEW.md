# Real Run Review

Use this file to review a real project run. Keep concrete examples. The goal is to decide the next engineering change based on evidence, not instinct.

## Run Metadata

- Date:
- Reviewer:
- Target project:
- Base branch:
- Compare branch:
- Diff file:
- Run artifact directory:
- State output:
- Initial result output:
- Merged result output:

## Input Context

- Approx diff line count:
- Changed file count:
- Requirements available: yes/no
- Specs available: yes/no
- Repo wiki available: yes/no
- Project profile available: yes/no
- Ignored dirs/files used:

## Preflight Review

- Preflight status:
- Missing required inputs:
- Warnings:
- Did missing context affect confidence?

## Cluster Overview

- Cluster count:
- Deep-analysis cluster count:
- Shallow cluster count:
- Unresolved changed files:
- Diagnostics:
- Noise file count:
- Files by noise kind:

## Noise Classification Review

| File | Noise Kind | Correct? | Why |
| --- | --- | --- | --- |
|  |  |  |  |

Questions:

- Did noise classification remove obvious format/comment/import-only changes?
- Did it remove generated files and lockfiles?
- Did it accidentally remove real product logic changes?
- Did noisy files still create clusters?

## Cluster Quality Review

| Cluster | Good/Bad | Why | Too Big? | Missing Evidence? | Action |
| --- | --- | --- | --- | --- | --- |
| cluster-001 |  |  |  |  |  |
| cluster-002 |  |  |  |  |  |

Questions:

- Are related files grouped together?
- Are unrelated changes split apart?
- Are shared components over-expanded?
- Are global/cross-cutting changes isolated instead of expanded to all pages?
- Are API changes grouped with meaningful callers/pages?
- Are route/page clusters easy to understand?

## Context Quality Review

Review 2 to 3 selected `cluster-context/*.json` files.

### Selected Cluster 1

- Cluster id:
- `diffEvidence` useful? yes/no
- `traceEvidence` useful? yes/no
- `routeEvidence` useful? yes/no
- `flowHints` useful? yes/no
- `codeEvidence` enough? yes/no
- `commentEvidence` useful? yes/no
- `documentCandidates` relevant? yes/no
- `riskHints` useful? yes/no
- `contextBudget.truncated`:
- Missing context:

### Selected Cluster 2

- Cluster id:
- `diffEvidence` useful? yes/no
- `traceEvidence` useful? yes/no
- `routeEvidence` useful? yes/no
- `flowHints` useful? yes/no
- `codeEvidence` enough? yes/no
- `commentEvidence` useful? yes/no
- `documentCandidates` relevant? yes/no
- `riskHints` useful? yes/no
- `contextBudget.truncated`:
- Missing context:

### Selected Cluster 3

- Cluster id:
- `diffEvidence` useful? yes/no
- `traceEvidence` useful? yes/no
- `routeEvidence` useful? yes/no
- `flowHints` useful? yes/no
- `codeEvidence` enough? yes/no
- `commentEvidence` useful? yes/no
- `documentCandidates` relevant? yes/no
- `riskHints` useful? yes/no
- `contextBudget.truncated`:
- Missing context:

## Claude Cluster Analysis Review

- How many cluster-analysis files were written:
- Did Claude open original source files? yes/no/examples
- Did Claude open original requirement/spec/wiki docs? yes/no/examples
- Did Claude keep analysis within cluster scope?
- Did Claude write uncertainties where evidence was weak?

Good example:

```text
Paste one strong case or analysis summary here.
```

Bad/generic example:

```text
Paste one weak case or analysis summary here.
```

## Merged Result Review

- `meta.analysisStatus`:
- Final case count:
- Missing-analysis cluster count:
- Validation issue count:
- Validation warning count:

Questions:

- Are cases specific enough for QA to execute?
- Does each case have a route/page entry?
- Does each case use route comments/meta titles instead of technical page names when available?
- Does each case have a clear user action?
- Does each case have concrete expected results?
- Does each case cite useful evidence?
- Are generic cases still present?
- Are uncertainties visible and useful?

## Validator Review

- Issues caught correctly:
- Warnings caught correctly:
- False positives:
- False negatives:
- Validator rules to add:
- Validator rules to relax:

## Product Judgment

Would a QA engineer trust this output?

- yes/no/partial

Why:

```text
Write a short judgment here.
```

## Next Engineering Actions

Choose the smallest useful next changes.

- [ ] Improve clustering
- [ ] Improve context collection
- [ ] Improve document retrieval
- [ ] Improve Claude agent/prompt instructions
- [ ] Improve cluster-analysis schema/examples
- [ ] Improve validator
- [ ] Add fixture/regression test from this run

Concrete action list:

1.
2.
3.
