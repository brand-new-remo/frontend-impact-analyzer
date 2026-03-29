from __future__ import annotations

from analyzer.case_builder import TestCaseBuilder
from analyzer.models import PageImpact


def test_case_builder_returns_sorted_case_array_shape():
    impact = PageImpact(
        changed_file="src/components/shared/SearchForm.tsx",
        page_file="src/pages/users/UserListPage.tsx",
        route_path="/users",
        module_name="users",
        trace=["src/components/shared/SearchForm.tsx", "src/pages/users/UserListPage.tsx"],
        impact_type="indirect",
        confidence="medium",
        impact_reason="shared-component changed, traced to page through 2 hop(s), semantics: button, form",
        semantic_tags=["button", "form", "disabled-state"],
    )

    cases = TestCaseBuilder().build([impact])
    output = [case.to_output_dict() for case in cases]

    assert [item["用例名称"] for item in output] == [
        "User List Page 页面基础回归",
        "User List Page 表单展示校验与提交流程验证",
        "User List Page 按钮入口与点击行为验证",
        "User List Page 禁用态与只读态验证",
    ]
    assert output[0]["页面名"] == "User List Page"
    assert output[0]["用例等级"] == "medium"
    assert output[0]["用例可置信度"] == "medium"
    assert "shared-component changed" in output[0]["来源描述"]
    assert "变更文件: src/components/shared/SearchForm.tsx" in output[0]["来源描述"]
