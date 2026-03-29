---
name: frontend-impact-analyzer
description: analyze react + react-router + vite front-end requirement text and git diff to identify impacted pages, routes, modules, and functions, then generate structured json test cases. use when chatgpt needs to assess front-end change impact, trace changed files upward through imports to top-level pages, interpret route relationships including nested routes and lazy imports, account for tsconfig path aliases and barrel exports, and output module-oriented test cases for testing.
---

# Frontend Impact Analyzer

Analyze requirement text and git diff for React + React Router + Vite projects and produce evidence-based impact analysis.

## Workflow

1. Save the provided requirement text and git diff into files if needed.
2. Sync the project environment with `uv sync`.
3. Run `uv run python scripts/front_end_impact_analyzer.py` with:
   - `--project-root`
   - `--diff-file`
   - optional `--requirement-file`
   - optional output paths
4. Read:
   - `impact-analysis-state.json` for evidence, traces, logs, and unresolved items
   - `impact-analysis-result.json` for the final JSON case array
5. Base the final answer on the generated JSON array. Do not invent impacted pages that are not supported by traces or route evidence.
6. If confidence is low, keep it low and explain why.

## Output rules

Return a JSON array only.

Each item should contain:
- `页面名`
- `用例名称`
- `测试步骤`
- `预期结果`
- `用例等级`
- `用例可置信度`
- `来源描述`

The current skill only generates the case array. It does not execute test cases.

## Heuristics

- Prefer page and route evidence over broad assumptions.
- For shared components, only expand impact to traced pages.
- For API changes, emphasize query, submit, detail, delete, export, and error handling where the analyzer tagged those semantics.
- For route changes, prioritize entry, navigation, access, refresh, and nested route behavior.
- For form and table semantics, generate function-oriented test cases instead of generic smoke tests.

## Resources

- Project conventions and extension ideas: `references/project-conventions.md`
- Impact and confidence rules: `references/impact-rules.md`
- Route tracing notes: `references/route-conventions.md`
