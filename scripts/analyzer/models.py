from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, TypedDict


class CaseOutput(TypedDict):
    页面名: str
    用例名称: str
    测试步骤: List[str]
    预期结果: List[str]
    用例等级: str
    用例可置信度: str
    来源描述: str


@dataclass
class ProcessLog:
    step: str
    status: str
    message: str
    ts: float = field(default_factory=time.time)


@dataclass
class ChangedFile:
    path: str
    change_type: str
    added_lines: int = 0
    removed_lines: int = 0
    symbols: List[str] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)
    file_type: str = "unknown"
    module_guess: str = "unknown"


@dataclass
class RouteInfo:
    route_path: Optional[str]
    source_file: str
    linked_page: Optional[str] = None
    route_component: Optional[str] = None
    parent_route: Optional[str] = None
    confidence: str = "medium"


@dataclass
class FileAstFacts:
    file: str
    imports: List[str] = field(default_factory=list)
    reexports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    component_names: List[str] = field(default_factory=list)
    hook_names: List[str] = field(default_factory=list)
    jsx_tags: List[str] = field(default_factory=list)
    jsx_props: List[str] = field(default_factory=list)
    route_paths: List[str] = field(default_factory=list)
    route_components: List[str] = field(default_factory=list)
    lazy_imports: List[str] = field(default_factory=list)
    api_calls: List[str] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class PageImpact:
    changed_file: str
    page_file: str
    route_path: Optional[str]
    module_name: str
    trace: List[str]
    impact_type: str
    confidence: str
    impact_reason: str
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class TestCase:
    page_name: str
    case_name: str
    test_steps: List[str]
    expected_results: List[str]
    case_level: str
    confidence: str
    source_description: str
    sort_priority: int = 99

    def to_output_dict(self) -> CaseOutput:
        return {
            "页面名": self.page_name,
            "用例名称": self.case_name,
            "测试步骤": self.test_steps,
            "预期结果": self.expected_results,
            "用例等级": self.case_level,
            "用例可置信度": self.confidence,
            "来源描述": self.source_description,
        }


@dataclass
class AnalysisState:
    meta: Dict = field(default_factory=dict)
    input: Dict = field(default_factory=dict)
    parsedDiff: Dict = field(default_factory=lambda: {"commitTypes": [], "changedFiles": []})
    codeGraph: Dict = field(default_factory=lambda: {
        "imports": {},
        "reverseImports": {},
        "pages": [],
        "routes": [],
        "astFacts": {},
        "aliases": {},
        "barrelFiles": [],
    })
    codeImpact: Dict = field(default_factory=lambda: {
        "fileClassifications": [],
        "pageImpacts": [],
        "unresolvedFiles": [],
        "sharedRisks": [],
    })
    businessImpact: Dict = field(default_factory=lambda: {
        "affectedModules": [],
        "affectedPages": [],
        "affectedFunctions": [],
    })
    output: List[CaseOutput] = field(default_factory=list)
    processLogs: List[Dict] = field(default_factory=list)


class ProcessRecorder:
    def __init__(self, state: AnalysisState):
        self.state = state

    def log(self, step: str, status: str, message: str):
        self.state.processLogs.append(asdict(ProcessLog(step=step, status=status, message=message)))


class StateStore:
    def __init__(self, state: AnalysisState):
        self.state = state

    def set_diff(self, commit_types, changed_files):
        self.state.parsedDiff["commitTypes"] = commit_types
        self.state.parsedDiff["changedFiles"] = [asdict(x) for x in changed_files]

    def set_graph(self, imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files):
        self.state.codeGraph["imports"] = imports
        self.state.codeGraph["reverseImports"] = reverse_imports
        self.state.codeGraph["pages"] = pages
        self.state.codeGraph["routes"] = [asdict(r) for r in routes]
        self.state.codeGraph["astFacts"] = ast_facts
        self.state.codeGraph["aliases"] = aliases
        self.state.codeGraph["barrelFiles"] = barrel_files

    def set_file_classifications(self, changed_files):
        self.state.codeImpact["fileClassifications"] = [
            {"file": x.path, "fileType": x.file_type, "moduleGuess": x.module_guess}
            for x in changed_files
        ]
