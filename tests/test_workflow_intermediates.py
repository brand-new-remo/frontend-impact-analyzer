from __future__ import annotations

import json
from pathlib import Path

from analyzer.cluster_tasks import build_cluster_task_markdown
from analyzer.context_collector import DocumentIndexer
from analyzer.result_merger import ClusterAnalysisMerger
from analyzer.workflow import build_run_manifest, load_config, sanitize_branch, write_default_config, write_json
from front_end_impact_analyzer import FrontendImpactAnalysisEngine


def test_default_config_can_be_written_and_loaded(tmp_path):
    config_path = tmp_path / "impact-analyzer.config.json"

    written = write_default_config(tmp_path, config_path)
    config = load_config(tmp_path, written)

    assert written == config_path
    assert config["paths"]["diffDir"] == ".impact-analysis/diffs"
    assert config["analysis"]["maxFilesPerClusterContext"] == 8


def test_manifest_uses_stable_branch_sanitization(tmp_path):
    config = load_config(tmp_path)
    manifest = build_run_manifest(
        tmp_path,
        config,
        base_branch="release/2026.04",
        compare_branch="feature/order batch",
        diff_file=tmp_path / "diff.patch",
        run_id=None,
    )

    assert sanitize_branch("feature/order batch") == "feature-order-batch"
    assert "release-2026.04_to_feature-order-batch" in manifest["runId"]
    assert manifest["diffFile"].endswith("diff.patch")


def test_cluster_builder_groups_by_page_trace():
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"
    diff_text = (root / "fixtures" / "diffs" / "shared_search_form.diff").read_text(encoding="utf-8")

    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    clusters = state.workflow["changeClusters"]["clusters"]
    assert len(clusters) == 1
    assert clusters[0]["candidatePages"] == ["src/pages/users/UserListPage.tsx"]
    assert clusters[0]["semanticTags"] == ["submit", "form", "button", "disabled-state"]
    assert state.workflow["diffIndex"]["files"][0]["changedLinePreview"]["added"]
    assert state.workflow["diffIndex"]["files"][0]["hunks"][0]["oldStart"] == 1
    assert state.workflow["diffIndex"]["files"][0]["hunks"][0]["newStart"] == 1
    assert "cluster-context/cluster-001.json" in state.workflow["clusterAnalysisTasks"]
    assert "cluster-analysis/cluster-001.analysis.json" in state.workflow["clusterAnalysisTasks"]
    assert state.workflow["clusterContexts"][0]["codeEvidence"][0]["whyIncluded"]
    assert "hunks" in state.workflow["clusterContexts"][0]["codeEvidence"][0]


def test_document_indexer_retrieves_cluster_related_snippets(tmp_path):
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    (req_dir / "order-batch-edit.md").write_text(
        "# 订单批量编辑\n\n点击批量编辑按钮后打开弹窗，提交成功后刷新订单列表。",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    config["paths"]["requirementsDir"] = "requirements"
    config["analysis"]["requireRepoWiki"] = False
    indexer = DocumentIndexer(tmp_path, config)
    document_index = indexer.build()

    matches = indexer.retrieve(
        document_index,
        {
            "title": "Order List Page impact cluster",
            "changedFiles": ["src/pages/order/ListPage.tsx"],
            "changedSymbols": ["handleBatchEdit"],
            "semanticTags": ["modal", "submit"],
            "candidateRoutes": ["/order/list"],
        },
    )

    assert document_index["documentCount"] == 1
    assert matches
    assert matches[0]["kind"] == "requirement"


def test_cluster_analysis_merger_only_outputs_claude_cases(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "cluster-analysis").mkdir(parents=True)
    write_json(run_dir / "00-run-manifest.json", {"runId": "run-demo"})
    write_json(run_dir / "90-coverage-report.json", {"totalChangedFiles": 1})
    write_json(run_dir / "05-change-clusters.json", {
        "clusters": [
            {
                "clusterId": "cluster-001",
                "title": "User List Page impact cluster",
                "candidatePages": ["src/pages/users/UserListPage.tsx"],
                "candidateRoutes": ["/users"],
                "confidence": "medium",
                "reason": "changed files trace to the same page",
                "seeds": [{"moduleGuess": "users"}],
            },
            {
                "clusterId": "cluster-002",
                "title": "Order Page impact cluster",
                "candidatePages": ["src/pages/orders/OrderPage.tsx"],
                "candidateRoutes": ["/orders"],
                "confidence": "low",
                "reason": "candidate module grouping",
                "seeds": [{"moduleGuess": "orders"}],
            },
        ]
    })
    write_json(run_dir / "99-final-result.json", {"cases": [], "fallbackCases": []})
    write_json(run_dir / "cluster-analysis" / "cluster-001.analysis.json", {
        "clusterId": "cluster-001",
        "changeIntent": "form-submit-flow",
        "userVisibleChange": "用户列表搜索表单提交链路发生变化",
        "affectedFunctionUnits": ["搜索提交"],
        "codeEvidenceUsed": [{"file": "src/components/shared/SearchForm.tsx"}],
        "docEvidenceUsed": [],
        "confidence": "high",
        "uncertainties": [],
        "cases": [
            {
                "pageName": "User List Page",
                "caseName": "用户列表搜索提交后刷新结果",
                "testSteps": ["进入用户列表", "输入搜索条件并提交"],
                "expectedResults": ["列表按搜索条件刷新"],
                "priority": "high",
                "confidence": "high",
            }
        ],
    })

    result = ClusterAnalysisMerger(run_dir).merge()

    assert result["meta"]["analysisStatus"] == "partial_success"
    assert result["summary"]["analyzedClusterCount"] == 1
    assert result["summary"]["missingAnalysisClusterCount"] == 1
    assert result["summary"]["fallbackCaseCount"] == 0
    assert result["cases"][0]["caseSource"] == "cluster-analysis"
    assert result["cases"][0]["caseName"] == "用户列表搜索提交后刷新结果"
    assert result["fallbackCases"] == []
    assert result["clusters"][1]["status"] == "missing-analysis"
    assert result["clusters"][1]["caseCount"] == 0


def test_cluster_task_markdown_contains_deep_and_merge_instructions():
    markdown = build_cluster_task_markdown(
        {
            "clusters": [
                {
                    "clusterId": "cluster-001",
                    "title": "Order List Page impact cluster",
                    "changedFiles": ["src/pages/orders/OrderListPage.tsx"],
                    "candidatePages": ["src/pages/orders/OrderListPage.tsx"],
                    "candidateRoutes": ["/orders"],
                    "semanticTags": ["table", "api"],
                    "changedSymbols": ["OrderListPage"],
                    "confidence": "high",
                    "reason": "changed files trace to the same candidate page",
                    "needsDeepAnalysis": True,
                }
            ]
        },
        {"totalChangedFiles": 1, "diagnosticCount": 0},
    )

    assert "Cluster Analysis Tasks" in markdown
    assert "cluster-context/cluster-001.json" in markdown
    assert "cluster-analysis/cluster-001.analysis.json" in markdown
    assert "--merge-cluster-analysis" in markdown


def test_sample_cluster_analysis_merges_to_snapshot(tmp_path):
    root = Path(__file__).resolve().parents[1]
    run_dir = tmp_path / "run-snapshot"
    (run_dir / "cluster-analysis").mkdir(parents=True)
    sample_analysis = json.loads((root / "fixtures" / "expected" / "sample_cluster_analysis.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "fixtures" / "expected" / "sample_merged_result.json").read_text(encoding="utf-8"))

    write_json(run_dir / "00-run-manifest.json", {"runId": "run-snapshot"})
    write_json(run_dir / "90-coverage-report.json", {"totalChangedFiles": 1})
    write_json(run_dir / "05-change-clusters.json", {
        "clusters": [
            {
                "clusterId": "cluster-001",
                "title": "User List Page impact cluster",
                "candidatePages": ["src/pages/users/UserListPage.tsx"],
                "candidateRoutes": ["/users"],
                "confidence": "medium",
                "reason": "changed files trace to the same candidate page and should be analyzed together",
                "seeds": [{"moduleGuess": "users"}],
            }
        ]
    })
    write_json(run_dir / "99-final-result.json", {"cases": []})
    write_json(run_dir / "cluster-analysis" / "cluster-001.analysis.json", sample_analysis)

    result = ClusterAnalysisMerger(run_dir).merge()
    result["clusterAnalyses"][0]["analysisFile"] = "__RUN_DIR__/cluster-analysis/cluster-001.analysis.json"

    assert result == expected
