---
name: frontend-impact-analyzer
description: analyze requirement text, git diff, and a local React/React Router/Vite codebase to generate an evidence-based JSON case array for QA. use when an agent needs to trace changed front-end files to concrete pages and routes, account for tsconfig aliases, barrel exports, nested routes, lazy routes, symbol-level usage, and api-field-level changes, then output sorted test-case items instead of prose.
---

# Frontend Impact Analyzer

Generate a JSON case array from front-end code changes.

This skill is for agents such as Codex or Claude Code that need to:
- inspect a React + React Router + Vite project
- analyze requirement text and git diff together
- trace change impact to concrete pages and routes
- convert technical impact into testable QA cases

This skill does:
- static analysis
- evidence-based page / route tracing
- conservative impact inference
- JSON case generation

This skill does not:
- execute test cases
- validate runtime behavior in a browser
- invent cases that are not supported by trace or route evidence
- treat pure formatting diffs as real impact

## When To Use

Use this skill when:
- the user provides requirement text, a PR diff, or a git diff
- the project is a React / React Router / Vite style front-end
- the goal is to produce QA-oriented test cases

Do not use this skill when:
- the user only wants prose explanation of a diff
- the target project is not a front-end app of this shape
- there is no local source tree to inspect

## Inputs

Expected inputs:
- `project_root`: local project root to scan
- `diff_file`: a file containing git diff / PR diff text
- `requirement_file`: optional requirement / design note text
- optional project profile document such as `project.md`: supplemental context only, not a source of hard-coded project-specific rules

Recommended preparation:
1. Save requirement text to a file if it exists.
2. Save diff content to a file.
3. Point `--project-root` at the real source tree being analyzed, not at this skill repo.

## Recommended Pre-Run Decision

Before running the analyzer, the calling agent should decide whether to generate a project profile file first.

Recommended agent prompt to the user:

```text
为了提升 alias、route、barrel、page 识别精度，是否要先生成一份项目画像文件？

- 选择“是”：会多一个前置步骤，但通常更适合目录结构复杂、monorepo、多端、非标准路由项目
- 选择“否”：直接开始分析，速度更快，但结果会更依赖源码静态分析本身
```

Decision rule:
- If the project is large, non-standard, monorepo-based, multi-app, or likely to have custom conventions, recommend generating the project profile first.
- If the project is small, conventional, or the user prefers speed, run the analyzer directly.
- If a project profile file already exists, reuse it instead of asking again unless the user wants to refresh it.

If the user chooses to generate one, treat the profile as:
- supplemental context
- a source of reusable patterns
- a hint layer, not a replacement for AST and trace evidence

Recommended file name:
- `impact-analyzer-project-profile.md`

Recommended minimum sections:
- `项目概览`
- `目录结构画像`
- `页面约定`
- `路由约定`
- `tsconfig / alias / import 约定`
- `barrel export 约定`
- `API 层约定`
- `shared component / business component / hooks / store 约定`
- `最重要的静态分析规则`
- `最容易误判的场景`
- `真实文件参考清单`

Profile authoring rules:
- Prefer real paths and real examples over abstract summaries.
- Mark unknowns explicitly instead of guessing.
- Separate reusable patterns from project-specific quirks.
- Do not rewrite the whole project architecture if only front-end-impact-relevant parts matter.
- Do not turn the profile into executable conclusions; it is supporting context only.

## Invocation

Preferred command:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --diff-file <diff_file> \
  --requirement-file <requirement_file> \
  --state-output impact-analysis-state.json \
  --result-output impact-analysis-result.json
```

Minimal command:

```bash
uv run python scripts/front_end_impact_analyzer.py \
  --project-root <target_project_root> \
  --diff-file <diff_file>
```

## Agent Workflow

1. Check whether a project profile file already exists.
2. If it does not exist, ask the user whether to generate one first.
3. Prepare diff and optional requirement files.
4. Run the analyzer.
5. Read `impact-analysis-state.json`.
6. Read `impact-analysis-result.json`.
7. Check `meta.analysisStatus`.
8. If status is `success` or `partial_success`, use the JSON case array as the primary result.
9. If status is `failed`, stop and surface the fatal diagnostic from state.

## Result Contract

The final result file is a JSON array only.

Each item contains:
- `页面名`
- `用例名称`
- `测试步骤`
- `预期结果`
- `用例等级`
- `用例可置信度`
- `来源描述`

The array is already sorted for downstream consumption.

Schemas:
- Result schema: `schemas/case-array.schema.json`
- State schema: `schemas/analysis-state.schema.json`

## State Contract

Read `impact-analysis-state.json` for:
- process logs
- parsed diff info
- import / reverse-import graph
- route binding evidence
- barrel evidence
- diagnostics
- unresolved files
- page impacts

Important fields:
- `meta.analysisStatus`
- `meta.statusSummary`
- `codeGraph.diagnostics`
- `codeImpact.unresolvedFiles`
- `codeImpact.pageImpacts`
- `codeImpact.sharedRisks`

Status meanings:
- `success`: analyzer completed and no unresolved files or diagnostics remain
- `partial_success`: analyzer completed but unresolved files or diagnostics exist
- `failed`: analyzer could not complete; state contains a fatal diagnostic

## Boundaries And Decision Rules

The agent using this skill should follow these rules:
- Prefer the generated JSON case array over freehand prose.
- Do not add pages or routes that are not supported by state evidence.
- If `partial_success`, keep the generated cases but explicitly surface unresolved files and diagnostics.
- If `failed`, do not invent fallback cases.
- If confidence is low, keep it low.
- If the diff is formatting-only, the analyzer may legitimately produce no cases.
- If a project profile document exists, use it to understand conventions, but extract reusable patterns rather than turning the skill into a project-specific adapter.

## What The Analyzer Understands

Current supported capabilities include:
- tsconfig alias resolution, including `extends`
- multi-target aliases
- barrel exports and multi-hop re-export traversal
- nested routes and lazy routes
- symbol-level first-hop filtering
- format-only diff skipping
- API field-level diff heuristics
- business-oriented case grouping

Current known limits:
- symbol-level tracing is strongest on the first hop and may still widen later in the graph
- wildcard alias edge cases are not fully covered
- API diff understanding is heuristic, not full schema diffing
- some dynamic route factories or generated routes may remain unresolved

## Recommended Agent Response Behavior

After running this skill:
- return the JSON case array when the user wants machine-readable output
- mention unresolved files or diagnostics when present
- avoid rewriting the cases into vague prose unless the user explicitly asks
- if a summary is needed, keep it short and anchor it to state evidence

## Prompt Template

Use this when another agent needs a ready-made instruction:

```text
Run the frontend-impact-analyzer skill against the target front-end project.

Inputs:
- project root: <target_project_root>
- diff file: <diff_file>
- requirement file: <requirement_file_or_none>
- project profile file: <project_profile_file_or_none>

Instructions:
1. If a project profile file does not already exist, ask the user whether to generate one first to improve analysis precision.
2. If the user agrees, generate the project profile file before running the analyzer.
3. Execute the analyzer with uv run.
4. Read both impact-analysis-state.json and impact-analysis-result.json.
5. Treat impact-analysis-result.json as the primary deliverable.
6. Do not invent pages, routes, or cases beyond what the state evidence supports.
7. If meta.analysisStatus is partial_success, keep the case array but also report unresolved files and diagnostics.
8. If meta.analysisStatus is failed, return the fatal diagnostic instead of inventing output.
9. Do not execute tests or browser flows; only generate the case array.
```

Recommended profile file conventions:
- File name: `impact-analyzer-project-profile.md`
- Focus on reusable front-end conventions, not one-off implementation details
- Include real route files, page files, API files, alias rules, and barrel patterns when possible

## Resources

- Project conventions and extension ideas: `references/project-conventions.md`
- Impact and confidence rules: `references/impact-rules.md`
- Route tracing notes: `references/route-conventions.md`
- Agent usage notes: `references/agent-usage.md`
