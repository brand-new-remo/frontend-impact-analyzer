from __future__ import annotations

import json
from pathlib import Path

from analyzer.cluster_tasks import build_cluster_task_markdown
from analyzer.context_collector import DocumentIndexer
from analyzer.result_merger import ClusterAnalysisMerger
from analyzer.workflow import build_run_manifest, doctor, install_claude_agents, load_config, sanitize_branch, write_default_config, write_json
from front_end_impact_analyzer import FrontendImpactAnalysisEngine


def test_default_config_can_be_written_and_loaded(tmp_path):
    config_path = tmp_path / "impact-analyzer.config.json"

    written = write_default_config(tmp_path, config_path)
    config = load_config(tmp_path, written)

    assert written == config_path
    assert config["paths"]["diffDir"] == ".impact-analysis/diffs"
    assert config["analysis"]["maxFilesPerClusterContext"] == 8
    assert config["analysis"]["maxClusterContextChars"] == 60000


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


def test_install_claude_agents_copies_templates_without_overwriting(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "change-intent-judge.md").write_text("new template", encoding="utf-8")
    (templates / "case-writer.md").write_text("case writer", encoding="utf-8")

    project = tmp_path / "project"
    project.mkdir()
    target_agents = project / ".claude" / "agents"
    target_agents.mkdir(parents=True)
    (target_agents / "change-intent-judge.md").write_text("existing", encoding="utf-8")

    report = install_claude_agents(project, templates_dir=templates)

    assert report["status"] == "ok"
    assert len(report["installed"]) == 1
    assert len(report["skipped"]) == 1
    assert (target_agents / "change-intent-judge.md").read_text(encoding="utf-8") == "existing"
    assert (target_agents / "case-writer.md").read_text(encoding="utf-8") == "case writer"

    overwrite_report = install_claude_agents(project, templates_dir=templates, overwrite=True)

    assert len(overwrite_report["installed"]) == 2
    assert (target_agents / "change-intent-judge.md").read_text(encoding="utf-8") == "new template"


def test_install_claude_agents_rejects_missing_project_root(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "change-intent-judge.md").write_text("template", encoding="utf-8")

    report = install_claude_agents(tmp_path / "missing-project", templates_dir=templates)

    assert report["status"] == "missing-project-root"
    assert not (tmp_path / "missing-project").exists()


def test_doctor_reports_recommended_uv_command(tmp_path):
    skill_root = Path(__file__).resolve().parents[1]
    report = doctor(tmp_path, skill_root)

    assert report["recommendedCommandPrefix"].startswith("uv run --project ")
    assert "scripts/front_end_impact_analyzer.py" in report["recommendedCommandPrefix"]
    assert any(check["name"] == "uv" for check in report["checks"])


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
    assert 'uv run --project "<skill_root>" python "<skill_root>/scripts/front_end_impact_analyzer.py"' in state.workflow["clusterAnalysisTasks"]
    assert state.workflow["clusterContexts"][0]["codeEvidence"][0]["whyIncluded"]
    assert "hunks" in state.workflow["clusterContexts"][0]["codeEvidence"][0]
    assert state.workflow["clusterContexts"][0]["traceEvidence"][0]["changedFile"] == "src/components/shared/SearchForm.tsx"
    assert state.workflow["clusterContexts"][0]["traceEvidence"][0]["candidatePage"] == "src/pages/users/UserListPage.tsx"
    assert state.workflow["clusterContexts"][0]["routeEvidence"][0]["routePath"] == "/users"
    assert state.workflow["clusterContexts"][0]["routeEvidence"][0]["displayName"] == "用户管理"
    assert state.workflow["clusterContexts"][0]["routeEvidence"][0]["routeComment"] == "用户列表"
    assert state.workflow["clusterContexts"][0]["flowHints"][0]["entry"]["route"] == "/users"
    assert "submit" in " ".join(state.workflow["clusterContexts"][0]["flowHints"][0]["possibleUserActions"])
    assert state.workflow["clusterContexts"][0]["commentEvidence"][0]["text"] == "提交后保留当前筛选条件"
    assert state.workflow["clusterContexts"][0]["commentEvidence"][0]["nearChangedHunk"] is True
    assert "Candidate business evidence" in state.workflow["clusterContexts"][0]["commentEvidence"][0]["usageGuidance"]
    assert state.workflow["clusterContexts"][0]["riskHints"][0]["kind"] == "shared-component"
    assert state.workflow["clusterContexts"][0]["contextBudget"]["maxChars"] == 60000
    assert state.workflow["clusterContexts"][0]["contextBudget"]["truncated"] is False


def test_noise_files_are_indexed_but_not_clustered():
    diff_text = """
chore: non logic changes

diff --git a/src/pages/users/UserListPage.tsx b/src/pages/users/UserListPage.tsx
index 1234567..89abcde 100644
--- a/src/pages/users/UserListPage.tsx
+++ b/src/pages/users/UserListPage.tsx
@@ -1,1 +1,1 @@
-// old note
+// new note
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
index 1234567..89abcde 100644
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -1,1 +1,1 @@
-foo: 1
+foo: 2
"""
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"

    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    assert state.workflow["diffIndex"]["totalChangedFiles"] == 2
    assert state.workflow["changeClusters"]["clusterCount"] == 0
    assert state.workflow["coverage"]["noiseFileCount"] == 2
    assert state.workflow["coverage"]["filesByNoiseKind"] == {
        "comment-only": 1,
        "lockfile": 1,
    }


def test_global_changes_are_clustered_without_page_expansion():
    diff_text = """
feat(app): adjust root provider

diff --git a/src/App.tsx b/src/App.tsx
index 1234567..89abcde 100644
--- a/src/App.tsx
+++ b/src/App.tsx
@@ -1,3 +1,4 @@
 export function App() {
-  return <RouterProvider />
+  return <AuthProvider><RouterProvider /></AuthProvider>
 }
"""
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"

    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    clusters = state.workflow["changeClusters"]["clusters"]
    assert len(clusters) == 1
    assert clusters[0]["scope"] == "global"
    assert clusters[0]["candidatePages"] == []
    assert clusters[0]["globalClassification"]["isGlobal"] is True
    assert clusters[0]["globalClassification"]["blastRadiusPolicy"] == "do-not-expand-to-all-pages"
    assert state.workflow["clusterContexts"][0]["riskHints"][0]["kind"] == "global-change"


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
    assert "matchedHeadings" in matches[0]
    assert matches[0]["candidateSnippets"][0]["heading"] == "订单批量编辑"


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
                "businessGoal": "验证搜索表单提交后列表按条件刷新",
                "entry": {"route": "/users", "page": "User List Page"},
                "testSteps": ["进入用户列表", "输入搜索条件并提交"],
                "expectedResults": ["列表按搜索条件刷新"],
                "evidence": [{"file": "src/components/shared/SearchForm.tsx"}],
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
    assert result["summary"]["validationIssueCount"] == 0
    assert result["summary"]["validationWarningCount"] == 0
    assert result["cases"][0]["caseSource"] == "cluster-analysis"
    assert result["cases"][0]["caseName"] == "用户列表搜索提交后刷新结果"
    assert result["cases"][0]["businessGoal"] == "验证搜索表单提交后列表按条件刷新"
    assert result["cases"][0]["entry"] == {"route": "/users", "page": "User List Page"}
    assert result["fallbackCases"] == []
    assert result["validationReports"][0]["status"] == "pass"
    assert result["clusters"][1]["status"] == "missing-analysis"
    assert result["clusters"][1]["caseCount"] == 0


def test_cluster_analysis_merger_prefers_route_display_name_when_page_name_missing(tmp_path):
    run_dir = tmp_path / "run-display-name"
    (run_dir / "cluster-analysis").mkdir(parents=True)
    write_json(run_dir / "00-run-manifest.json", {"runId": "run-display-name"})
    write_json(run_dir / "90-coverage-report.json", {"totalChangedFiles": 1})
    write_json(run_dir / "98-analysis-state.json", {
        "codeGraph": {
            "routes": [
                {
                    "route_path": "/users",
                    "linked_page": "src/pages/users/UserListPage.tsx",
                    "display_name": "用户管理",
                }
            ]
        }
    })
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
            }
        ]
    })
    write_json(run_dir / "cluster-analysis" / "cluster-001.analysis.json", {
        "clusterId": "cluster-001",
        "changeIntent": "form-submit-flow",
        "userVisibleChange": "用户搜索提交变化",
        "affectedFunctionUnits": ["搜索提交"],
        "codeEvidenceUsed": [{"file": "src/components/shared/SearchForm.tsx"}],
        "docEvidenceUsed": [],
        "confidence": "medium",
        "uncertainties": [],
        "cases": [
            {
                "caseName": "用户搜索提交后刷新结果",
                "testSteps": ["进入用户管理", "输入条件并提交"],
                "expectedResults": ["列表按条件刷新"],
                "evidence": [{"file": "src/components/shared/SearchForm.tsx"}],
            }
        ],
    })

    result = ClusterAnalysisMerger(run_dir).merge()

    assert result["cases"][0]["pageName"] == "用户管理"


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
