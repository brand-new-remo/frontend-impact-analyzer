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
        "- Inspect documentCandidates and open original repo-wiki/requirement/spec files when snippets are ambiguous.",
        "- Do not broaden scope beyond code and document evidence.",
        "- Put uncertain claims into `uncertainties` instead of turning them into test cases.",
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
        "- `cases`",
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
        "```bash",
        "uv run python scripts/front_end_impact_analyzer.py \\",
        "  --project-root <target_project_root> \\",
        "  --merge-cluster-analysis \\",
        "  --run-dir <run_artifact_dir> \\",
        "  --result-output impact-analysis-merged-result.json",
        "```",
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
        "2. Identify the precise user-visible change.",
        "3. List affected function units.",
        "4. Cite code evidence and document evidence.",
        "5. Generate only evidence-backed cases.",
        "6. Record uncertainties for anything not directly supported.",
        "",
    ])
    return lines
