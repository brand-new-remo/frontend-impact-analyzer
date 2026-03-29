#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from analyzer.case_builder import TestCaseBuilder
from analyzer.common import uniq_keep_order
from analyzer.diff_parser import GitDiffParser
from analyzer.impact_engine import ImpactAnalyzer
from analyzer.models import AnalysisState, ProcessRecorder, StateStore
from analyzer.project_scanner import ProjectScanner
from analyzer.source_classifier import SourceClassifier


class FrontendImpactAnalysisEngine:
    def __init__(self, project_root: Path, diff_text: str, requirement_text: str = ""):
        self.project_root = project_root
        self.diff_text = diff_text
        self.requirement_text = requirement_text
        self.state = AnalysisState(
            meta={
                "projectType": "react-vite-react-router",
                "analysisTime": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            },
            input={
                "requirementText": requirement_text,
                "gitDiffText": diff_text,
            },
        )
        self.recorder = ProcessRecorder(self.state)
        self.store = StateStore(self.state)

    def run(self) -> AnalysisState:
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
        imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files = scanner.scan()
        self.recorder.log("scan_project", "done", f"scanned {len(imports)} source files, found {len(pages)} pages, {len(routes)} routes")
        self.store.set_graph(imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files)

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

        self.recorder.log("build_cases", "running", "start building test cases")
        cases = TestCaseBuilder().build(page_impacts)
        self.recorder.log("build_cases", "done", f"generated {len(cases)} cases")

        self.state.output = [c.to_output_dict() for c in cases]
        return self.state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--diff-file", required=True)
    parser.add_argument("--requirement-file")
    parser.add_argument("--state-output", default="impact-analysis-state.json")
    parser.add_argument("--result-output", default="impact-analysis-result.json")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    diff_text = Path(args.diff_file).read_text(encoding="utf-8", errors="ignore")
    requirement_text = Path(args.requirement_file).read_text(encoding="utf-8", errors="ignore") if args.requirement_file else ""

    state = FrontendImpactAnalysisEngine(project_root, diff_text, requirement_text).run()
    Path(args.state_output).write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.result_output).write_text(json.dumps(state.output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"state written to: {args.state_output}")
    print(f"result written to: {args.result_output}")


if __name__ == "__main__":
    main()
