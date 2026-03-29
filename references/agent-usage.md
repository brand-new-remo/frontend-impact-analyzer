# Agent Usage Notes

## Goal

This skill is designed for agent-to-tool usage, not for human-only reading.

The primary output is:
- a sorted JSON case array

The supporting output is:
- a state JSON file with evidence and diagnostics

## Recommended Agent Pattern

1. Check whether a project profile file already exists.
2. If it does not exist, ask the user whether to generate one first.
3. Prepare diff and optional requirement files.
4. Run the analyzer.
5. Inspect `meta.analysisStatus`.
6. Consume `impact-analysis-result.json` as the result.
7. Inspect state only for:
   - unresolved files
   - diagnostics
   - route binding evidence
   - shared risks
8. If a project profile document like `project.md` exists, use it only as supplemental context for conventions and edge cases.

Recommended ask-before-run prompt:

```text
为了提升 alias、route、barrel、page 识别精度，是否要先生成一份项目画像文件？

- 选择“是”：更适合复杂项目，但会多一个前置步骤
- 选择“否”：直接开始分析，速度更快
```

Recommended project profile conventions:
- Recommended file name: `impact-analyzer-project-profile.md`
- Keep the profile focused on front-end-impact-relevant structure and conventions
- Prefer real paths, real files, and real examples
- Explicitly separate reusable patterns from project-specific quirks
- Treat the profile as hints and context, not as a replacement for static analysis

## If Status Is `success`

- Use the case array directly.

## If Status Is `partial_success`

- Use the case array directly.
- Also surface:
  - `codeImpact.unresolvedFiles`
  - `codeGraph.diagnostics`
  - `codeImpact.sharedRisks`

## If Status Is `failed`

- Do not invent fallback output.
- Read the fatal diagnostic from `codeGraph.diagnostics`.

## Output Discipline

- Do not reclassify formatting-only changes as real impact.
- Do not expand shared-component changes to unrelated pages.
- Do not add unsupported pages or routes.
- Do not execute test cases.
- Do not hard-code one target project's folder structure or naming rules into this skill. Extract generalizable patterns instead.

## Good Downstream Usage

- import the JSON array into another QA/planning step
- hand the array to another skill for formatting, export, or execution
- summarize only after reading state diagnostics
