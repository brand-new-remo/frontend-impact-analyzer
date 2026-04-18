#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from analyzer.cluster_builder import ChangeClusterBuilder
from analyzer.cluster_tasks import build_cluster_task_markdown
from analyzer.common import uniq_keep_order
from analyzer.context_collector import ClusterContextCollector, DocumentIndexer
from analyzer.diff_parser import GitDiffParser
from analyzer.impact_engine import ImpactAnalyzer
from analyzer.models import AnalysisState, ProcessRecorder, StateStore
from analyzer.project_scanner import ProjectScanner
from analyzer.result_merger import ClusterAnalysisMerger
from analyzer.source_classifier import SourceClassifier
from analyzer.workflow import build_run_manifest, ensure_run_dir, load_config, make_diff_file, preflight, write_default_config, write_json


class FrontendImpactAnalysisEngine:
    def __init__(
        self,
        project_root: Path,
        diff_text: str,
        requirement_text: str = "",
        config: dict | None = None,
        manifest: dict | None = None,
        preflight_report: dict | None = None,
    ):
        self.project_root = project_root
        self.diff_text = diff_text
        self.requirement_text = requirement_text
        self.config = config or load_config(project_root)
        self.manifest = manifest or build_run_manifest(project_root, self.config, None, None, None)
        self.preflight_report = preflight_report or preflight(project_root, self.config)
        self.state = AnalysisState(
            meta={
                "projectType": "react-vite-react-router",
                "analysisTime": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                "analysisStatus": "running",
                "outputContract": "analysis-package-v2",
                "stateSchema": "schemas/analysis-state.schema.json",
                "resultSchema": "schemas/analysis-result.schema.json",
            },
            input={
                "requirementText": requirement_text,
                "gitDiffText": diff_text,
            },
        )
        self.recorder = ProcessRecorder(self.state)
        self.store = StateStore(self.state)

    def run(self) -> AnalysisState:
        self.state.workflow["manifest"] = self.manifest
        self.state.workflow["preflight"] = self.preflight_report

        self.recorder.log("parse_diff", "running", "start parsing diff")
        commit_types, changed_files = GitDiffParser(self.diff_text).parse()
        self.recorder.log("parse_diff", "done", f"parsed {len(changed_files)} changed files")

        classifier = SourceClassifier()
        for cf in changed_files:
            cf.file_type = classifier.classify(cf.path)
            cf.module_guess = classifier.guess_module(cf.path)
        self.store.set_diff(commit_types, changed_files)
        self.store.set_file_classifications(changed_files)

        self.recorder.log("scan_project", "running", "start scanning project with AST")
        scanner = ProjectScanner(self.project_root)
        imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files, barrel_evidence, diagnostics = scanner.scan()
        self.recorder.log("scan_project", "done", f"scanned {len(imports)} source files, found {len(pages)} pages, {len(routes)} routes")
        self.store.set_graph(imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files, barrel_evidence, diagnostics)

        self.recorder.log("impact_analysis", "running", "start tracing changed files to pages")
        analyzer = ImpactAnalyzer(imports=imports, reverse_imports=reverse_imports, pages=pages, routes=routes, ast_facts=ast_facts)
        page_impacts = []
        unresolved = []
        for cf in changed_files:
            impacts, unresolved_item = analyzer.analyze_file(cf)
            page_impacts.extend(impacts)
            if unresolved_item:
                unresolved.append(unresolved_item)
        self.state.codeImpact["pageImpacts"] = [asdict(x) for x in page_impacts]
        self.state.codeImpact["unresolvedFiles"] = unresolved
        self.state.codeImpact["sharedRisks"] = [
            {
                "file": cf.path,
                "risk": "shared component change may affect multiple pages but should be validated based on actual trace and semantics",
                "confidence": "medium",
            }
            for cf in changed_files if cf.file_type == "shared-component"
        ]
        self.recorder.log("impact_analysis", "done", f"generated {len(page_impacts)} page impacts")

        affected_modules = uniq_keep_order([x.module_name for x in page_impacts if x.module_name])
        affected_pages = uniq_keep_order([x.page_file for x in page_impacts if x.page_file])
        affected_functions = uniq_keep_order([tag for x in page_impacts for tag in x.semantic_tags])
        self.state.businessImpact["affectedModules"] = affected_modules
        self.state.businessImpact["affectedPages"] = affected_pages
        self.state.businessImpact["affectedFunctions"] = affected_functions

        self.recorder.log("build_intermediates", "running", "start building diff index and change clusters")
        cluster_builder = ChangeClusterBuilder(self.diff_text)
        diff_index = cluster_builder.build_diff_index(changed_files)
        seeds = cluster_builder.build_file_impact_seeds(changed_files, page_impacts, unresolved)
        clusters = cluster_builder.build_clusters(
            seeds,
            max_deep_clusters=int(self.config["analysis"].get("maxClustersForDeepAnalysis", 30)),
        )
        document_index = DocumentIndexer(self.project_root, self.config).build()
        context_collector = ClusterContextCollector(
            self.project_root,
            self.config,
            imports=imports,
            reverse_imports=reverse_imports,
            ast_facts=ast_facts,
            document_index=document_index,
        )
        cluster_contexts = [context_collector.collect(cluster, diff_index) for cluster in clusters.get("clusters", [])]
        coverage = cluster_builder.build_coverage(diff_index, clusters, diagnostics)
        cluster_tasks = build_cluster_task_markdown(clusters, coverage)
        self.state.workflow["diffIndex"] = diff_index
        self.state.workflow["fileImpactSeeds"] = seeds
        self.state.workflow["documentIndex"] = document_index
        self.state.workflow["changeClusters"] = clusters
        self.state.workflow["clusterAnalysisTasks"] = cluster_tasks
        self.state.workflow["clusterContexts"] = cluster_contexts
        self.state.workflow["coverage"] = coverage
        self.recorder.log("build_intermediates", "done", f"generated {len(clusters.get('clusters', []))} change clusters")

        self.recorder.log("build_cases", "skipped", "cases require Claude cluster-analysis; no template cases generated")

        self.state.output = self._build_analysis_package(clusters, coverage, document_index)
        self.state.meta["analysisStatus"] = self._analysis_status(page_impacts, unresolved, diagnostics)
        self.state.meta["statusSummary"] = {
            "changedFileCount": len(changed_files),
            "pageImpactCount": len(page_impacts),
            "caseCount": 0,
            "unresolvedFileCount": len(unresolved),
            "diagnosticCount": len(diagnostics),
        }
        self.state.output["meta"]["analysisStatus"] = self.state.meta["analysisStatus"]
        self.state.output["summary"]["statusSummary"] = self.state.meta["statusSummary"]
        return self.state

    def write_run_artifacts(self, run_dir: Path, state: AnalysisState) -> None:
        write_json(run_dir / "00-run-manifest.json", state.workflow["manifest"])
        write_json(run_dir / "01-preflight-report.json", state.workflow["preflight"])
        write_json(run_dir / "02-document-index.json", state.workflow.get("documentIndex", {}))
        write_json(run_dir / "03-diff-index.json", state.workflow["diffIndex"])
        write_json(run_dir / "04-file-impact-seeds.json", state.workflow["fileImpactSeeds"])
        write_json(run_dir / "05-change-clusters.json", state.workflow["changeClusters"])
        (run_dir / "06-cluster-analysis-tasks.md").write_text(state.workflow["clusterAnalysisTasks"], encoding="utf-8")
        for context in state.workflow["clusterContexts"]:
            write_json(run_dir / "cluster-context" / f"{context['clusterId']}.json", context)
        write_json(run_dir / "90-coverage-report.json", state.workflow["coverage"])
        write_json(run_dir / "99-final-result.json", state.output)

    def _analysis_status(self, page_impacts, unresolved, diagnostics):
        if self.preflight_report.get("status") == "blocked":
            return "partial_success"
        if page_impacts:
            if unresolved or diagnostics:
                return "partial_success"
            return "success"
        if unresolved or diagnostics:
            return "partial_success"
        return "success"

    def _build_analysis_package(self, clusters, coverage, document_index):
        cluster_summaries = []
        for cluster in clusters.get("clusters", []):
            cluster_summaries.append({
                "clusterId": cluster["clusterId"],
                "title": cluster["title"],
                "changedFiles": cluster["changedFiles"],
                "candidatePages": cluster["candidatePages"],
                "candidateRoutes": cluster["candidateRoutes"],
                "semanticTags": cluster["semanticTags"],
                "confidence": cluster["confidence"],
                "needsDeepAnalysis": cluster["needsDeepAnalysis"],
                "reason": cluster["reason"],
                "recommendedClaudeTask": (
                    "Read this cluster's context JSON, inspect relevant original documents if snippets are insufficient, "
                    "then determine the precise user-visible change and produce evidence-backed QA cases."
                ),
            })
        return {
            "meta": {
                "outputContract": "analysis-package-v2",
                "runId": self.manifest.get("runId"),
                "analysisStatus": "running",
            },
            "summary": {
                "affectedModules": self.state.businessImpact["affectedModules"],
                "affectedPages": self.state.businessImpact["affectedPages"],
                "affectedFunctions": self.state.businessImpact["affectedFunctions"],
                "caseCount": 0,
                "fallbackCaseCount": 0,
                "missingAnalysisClusterCount": len([cluster for cluster in clusters.get("clusters", []) if cluster.get("needsDeepAnalysis")]),
                "clusterCount": clusters.get("clusterCount", 0),
                "documentCount": document_index.get("documentCount", 0),
            },
            "coverage": coverage,
            "clusters": cluster_summaries,
            "cases": [],
            "fallbackCases": [],
            "nextStepsForClaude": [
                "Read 05-change-clusters.json and prioritize clusters with needsDeepAnalysis=true.",
                "For each prioritized cluster, read cluster-context/<clusterId>.json.",
                "Use documentCandidates as evidence candidates; open the original requirement/spec/wiki files when snippets are ambiguous.",
                "Write cluster-analysis/<clusterId>.analysis.json with changeIntent, userVisibleChange, evidence, confidence, uncertainties, and cases.",
                "Use 06-cluster-analysis-tasks.md as the cluster work queue.",
                "Run --merge-cluster-analysis with --run-dir to merge Claude-written cluster analyses into final cases.",
                "Use merged cases as final QA output; clusters missing Claude analysis produce no cases.",
            ],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--diff-file")
    parser.add_argument("--requirement-file")
    parser.add_argument("--config-file")
    parser.add_argument("--project-profile-file")
    parser.add_argument("--init-config", action="store_true")
    parser.add_argument("--make-diff", action="store_true")
    parser.add_argument("--base-branch")
    parser.add_argument("--compare-branch")
    parser.add_argument("--ignore-dir", action="append", default=[])
    parser.add_argument("--analysis-output-dir")
    parser.add_argument("--merge-cluster-analysis", action="store_true")
    parser.add_argument("--run-dir")
    parser.add_argument("--state-output", default="impact-analysis-state.json")
    parser.add_argument("--result-output", default="impact-analysis-result.json")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if args.merge_cluster_analysis:
        if not args.run_dir:
            raise SystemExit("--run-dir is required with --merge-cluster-analysis")
        result = ClusterAnalysisMerger(Path(args.run_dir).resolve()).write(Path(args.result_output).resolve())
        print(f"merged result written to: {args.result_output}")
        print(f"analysis status: {result['meta']['analysisStatus']}")
        return

    config_file = Path(args.config_file).resolve() if args.config_file else None
    if args.init_config:
        path = write_default_config(project_root, config_file)
        print(f"config written to: {path}")
        return

    config = load_config(project_root, config_file)
    if args.analysis_output_dir:
        config["paths"]["outputDir"] = args.analysis_output_dir
    if args.project_profile_file:
        config["paths"]["projectProfileFile"] = args.project_profile_file

    diff_file = Path(args.diff_file).resolve() if args.diff_file else None
    if args.make_diff:
        base = args.base_branch or config["project"].get("defaultBaseBranch") or "main"
        compare = args.compare_branch or config["project"].get("defaultCompareBranch") or "HEAD"
        diff_file = make_diff_file(project_root, config, base, compare, args.ignore_dir)
    if diff_file is None:
        raise SystemExit("--diff-file is required unless --make-diff is used")

    diff_text = diff_file.read_text(encoding="utf-8", errors="ignore")
    requirement_text = Path(args.requirement_file).read_text(encoding="utf-8", errors="ignore") if args.requirement_file else ""
    manifest = build_run_manifest(project_root, config, args.base_branch, args.compare_branch, diff_file)
    run_dir = ensure_run_dir(manifest)
    preflight_report = preflight(project_root, config)

    engine = FrontendImpactAnalysisEngine(project_root, diff_text, requirement_text, config=config, manifest=manifest, preflight_report=preflight_report)
    try:
        state = engine.run()
        state.output["meta"]["analysisStatus"] = state.meta["analysisStatus"]
        engine.write_run_artifacts(run_dir, state)
        exit_code = 0
    except Exception as exc:
        engine.recorder.log("analysis", "failed", str(exc))
        engine.state.meta["analysisStatus"] = "failed"
        engine.state.meta["statusSummary"] = {
            "changedFileCount": 0,
            "pageImpactCount": 0,
            "caseCount": 0,
            "unresolvedFileCount": 0,
            "diagnosticCount": 1,
        }
        engine.state.codeGraph["diagnostics"].append({
            "type": "fatal-error",
            "file": "",
            "target": "",
            "message": str(exc),
        })
        state = engine.state
        exit_code = 1

    Path(args.state_output).write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.result_output).write_text(json.dumps(state.output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"run artifacts written to: {run_dir}")
    print(f"state written to: {args.state_output}")
    print(f"result written to: {args.result_output}")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
