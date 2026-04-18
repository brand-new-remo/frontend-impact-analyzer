from __future__ import annotations

from typing import Dict, List


def build_cluster_task_markdown(clusters_data: Dict, coverage: Dict) -> str:
    clusters = clusters_data.get("clusters", [])
    deep_clusters = [cluster for cluster in clusters if cluster.get("needsDeepAnalysis")]
    shallow_clusters = [cluster for cluster in clusters if not cluster.get("needsDeepAnalysis")]

    lines: List[str] = [
        "# Cluster Analysis Tasks",
        "",
        "Use this file as the work queue for Claude Code cluster-level analysis.",
        "",
        "## Coverage",
        "",
        f"- Total changed files: {coverage.get('totalChangedFiles', 0)}",
        f"- Deep analysis clusters: {len(deep_clusters)}",
        f"- Shallow clusters: {len(shallow_clusters)}",
        f"- Diagnostics: {coverage.get('diagnosticCount', 0)}",
        "",
        "## Rules",
        "",
        "- Analyze one cluster at a time.",
        "- Read the cluster context JSON before writing analysis.",
        "- Inspect diffEvidence, traceEvidence, routeEvidence, flowHints, riskHints, codeEvidence, and documentCandidates.",
        "- Open original repo-wiki/requirement/spec files when snippets or matched headings are ambiguous.",
        "- Do not broaden scope beyond code and document evidence.",
        "- Put uncertain claims into `uncertainties` instead of turning them into test cases.",
        "- Avoid generic smoke/regression cases; every case needs a clear user action and evidence.",
        "- Write output to `cluster-analysis/<clusterId>.analysis.json`.",
        "",
        "## Output Contract",
        "",
        "Each cluster analysis file must match `schemas/cluster-analysis.schema.json` and include:",
        "",
        "- `clusterId`",
        "- `changeIntent`",
        "- `userVisibleChange`",
        "- `affectedFunctionUnits`",
        "- `codeEvidenceUsed`",
        "- `docEvidenceUsed`",
        "- `confidence`",
        "- `uncertainties`",
        "- `cases` with clear user actions, expected results, and evidence",
        "",
        "## Deep Analysis Queue",
        "",
    ]

    if not deep_clusters:
        lines.extend(["No clusters require deep analysis.", ""])
    else:
        for idx, cluster in enumerate(deep_clusters, start=1):
            lines.extend(_cluster_task_block(idx, cluster, "deep"))

    lines.extend([
        "## Shallow / Fallback Queue",
        "",
    ])
    if not shallow_clusters:
        lines.extend(["No shallow clusters.", ""])
    else:
        for idx, cluster in enumerate(shallow_clusters, start=1):
            lines.extend(_cluster_task_block(idx, cluster, "shallow"))

    lines.extend([
        "## Merge After Analysis",
        "",
        "After writing cluster-analysis files, run:",
        "",
        "```text",
        'uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py" --project-root "<target_project_root>" --merge-cluster-analysis --run-dir "<run_artifact_dir>"',
        "```",
        "",
        "## Refine Final Cases",
        "",
        "After merge, optionally use the `case-refiner` agent to write `99-refined-cases.json`.",
        "",
        "Refinement rules:",
        "",
        "- Read `99-merged-result.json`, `validationReports`, `05-change-clusters.json`, and `cluster-analysis/*.analysis.json`.",
        "- Preserve each case's testing intent, user operation flow, expected behavior, evidence, priority, and confidence.",
        "- Only improve wording, dedupe, reorder, split overlong cases, or remove unsupported/generic cases.",
        "- Do not add new business scope, pages, routes, expectations, or cases without existing evidence.",
        "- Output must match `schemas/refined-cases.schema.json`.",
        "",
    ])
    return "\n".join(lines)


def _cluster_task_block(index: int, cluster: Dict, queue: str) -> List[str]:
    cluster_id = cluster.get("clusterId", f"cluster-{index:03d}")
    changed_files = cluster.get("changedFiles", [])
    pages = cluster.get("candidatePages", [])
    routes = cluster.get("candidateRoutes", [])
    tags = cluster.get("semanticTags", [])
    symbols = cluster.get("changedSymbols", [])
    lines = [
        f"### {index}. {cluster_id}: {cluster.get('title', '')}",
        "",
        f"- Queue: `{queue}`",
        f"- Confidence: `{cluster.get('confidence', 'low')}`",
        f"- Reason: {cluster.get('reason', '')}",
        f"- Context input: `cluster-context/{cluster_id}.json`",
        f"- Analysis output: `cluster-analysis/{cluster_id}.analysis.json`",
        f"- Candidate pages: {', '.join(pages) if pages else 'none'}",
        f"- Candidate routes: {', '.join(routes) if routes else 'none'}",
        f"- Semantic tags: {', '.join(tags) if tags else 'none'}",
        f"- Changed symbols: {', '.join(symbols) if symbols else 'none'}",
        "",
        "Changed files:",
        "",
    ]
    if changed_files:
        lines.extend([f"- `{path}`" for path in changed_files])
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Required analysis steps:",
        "",
        "1. Read the context input.",
        "2. Use `flowHints` to understand possible entry routes, user actions, and state changes, but treat them as hints.",
        "3. Open source files or original documents when the context snippets are insufficient.",
        "4. Identify the precise user-visible change.",
        "5. List affected function units.",
        "6. Cite code evidence and document evidence.",
        "7. Generate only evidence-backed cases with explicit user actions and expected results.",
        "8. Record uncertainties for anything not directly supported.",
        "",
    ])
    return lines
