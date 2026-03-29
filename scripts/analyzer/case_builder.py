from __future__ import annotations

from typing import List

from .common import confidence_to_priority, title_from_file, uniq_keep_order
from .models import PageImpact, TestCase


class TestCaseBuilder:
    def build(self, impacts: List[PageImpact]) -> List[TestCase]:
        cases: List[TestCase] = []
        for impact in impacts:
            cases.extend(self._build_cases_for_impact(impact))
        return self._dedupe(cases)

    def _build_cases_for_impact(self, impact: PageImpact) -> List[TestCase]:
        semantics = set(impact.semantic_tags)
        page_name = title_from_file(impact.page_file)
        groups = [self._base_case(impact, page_name)]
        mapping = [
            ("button", self._button_case),
            ("modal", self._modal_case),
            ("form", self._form_case),
            ("validation", self._form_case),
            ("table", self._table_case),
            ("columns", self._table_case),
            ("api", self._api_case),
            ("list-query", self._query_case),
            ("detail", self._detail_case),
            ("delete", self._delete_case),
            ("permission", self._permission_case),
            ("navigation", self._navigation_case),
            ("upload", self._upload_case),
            ("disabled-state", self._disabled_case),
            ("route", self._navigation_case),
        ]
        for tag, builder in mapping:
            if tag in semantics:
                groups.append(builder(impact, page_name))
        return groups

    def _mk(self, impact: PageImpact, page_name: str, case_name: str, steps, expected, sort_priority: int) -> TestCase:
        source_parts = [impact.impact_reason]
        if impact.route_path:
            source_parts.append(f"关联路由: {impact.route_path}")
        if impact.changed_file:
            source_parts.append(f"变更文件: {impact.changed_file}")
        return TestCase(
            page_name=page_name,
            case_name=case_name,
            test_steps=steps,
            expected_results=expected,
            case_level=confidence_to_priority(impact.confidence),
            confidence=impact.confidence,
            source_description="；".join(source_parts),
            sort_priority=sort_priority,
        )

    def _base_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 页面基础回归", [f"进入页面 {page_name}", "观察页面初始化渲染"], ["页面可正常加载", "页面无报错、无白屏、无异常提示"], 10)
    def _button_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 按钮入口与点击行为验证", [f"进入页面 {page_name}", "定位相关按钮", "点击按钮触发操作"], ["按钮展示符合预期", "按钮可点击性符合预期", "点击后行为符合需求"], 30)
    def _modal_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 弹窗打开关闭与提交验证", [f"进入页面 {page_name}", "触发弹窗打开", "执行确认与取消操作"], ["弹窗可正常打开", "弹窗内容展示正确", "确认与取消行为符合预期"], 25)
    def _form_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 表单展示校验与提交流程验证", [f"进入页面 {page_name}", "填写表单", "触发表单校验", "提交表单"], ["表单字段展示正确", "必填/格式校验符合预期", "提交成功或失败提示符合预期"], 20)
    def _table_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 列表列展示与表格交互验证", [f"进入页面 {page_name}", "检查列表列展示", "验证列表选择/操作列行为"], ["表格列展示正确", "操作列交互正常", "选择与点击行为符合预期"], 22)
    def _api_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 接口调用与页面反馈验证", [f"进入页面 {page_name}", "触发页面主要数据请求或提交请求", "观察页面反馈"], ["请求参数符合预期", "成功返回后的页面渲染正确", "异常返回时提示与容错符合预期"], 15)
    def _query_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 查询筛选分页排序验证", [f"进入页面 {page_name}", "执行查询/筛选/分页/排序操作"], ["查询条件生效", "分页行为正确", "筛选排序结果符合预期"], 18)
    def _detail_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 详情展示与回显验证", [f"进入页面 {page_name}", "进入详情或编辑态", "检查字段展示与回显"], ["详情展示正确", "编辑态回显正确", "字段映射符合预期"], 24)
    def _delete_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 删除流程与结果反馈验证", [f"进入页面 {page_name}", "触发删除操作", "确认删除"], ["删除确认交互正确", "删除成功后数据状态正确", "删除失败时提示正确"], 28)
    def _permission_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 权限可见性与可操作性验证", [f"分别使用不同权限账号进入页面 {page_name}", "检查页面入口、按钮、字段可见性与可操作性"], ["不同角色下页面可见性符合预期", "按钮与操作权限符合预期"], 12)
    def _navigation_case(self, impact, page_name):
        desc = f" 路由 {impact.route_path}" if impact.route_path else ""
        return self._mk(impact, page_name, f"{page_name}{desc} 进入跳转与返回验证", [f"进入页面 {page_name}", "执行页面跳转", "刷新页面并执行返回"], ["页面入口可正常访问", "跳转链路正确", "刷新与返回行为符合预期"], 14)
    def _upload_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 上传流程验证", [f"进入页面 {page_name}", "执行文件上传"], ["上传前校验正确", "上传成功与失败反馈正确"], 26)
    def _disabled_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 禁用态与只读态验证", [f"进入页面 {page_name}", "观察控件禁用态或只读态", "尝试触发操作"], ["禁用态展示正确", "不可操作时拦截正确", "可操作条件下行为恢复正常"], 32)

    def _dedupe(self, cases: List[TestCase]) -> List[TestCase]:
        out: List[TestCase] = []
        seen = set()
        for c in cases:
            key = (c.page_name, c.case_name)
            if key not in seen:
                seen.add(key)
                out.append(c)
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            out,
            key=lambda c: (
                c.page_name,
                c.sort_priority,
                priority_rank.get(c.case_level, 99),
                priority_rank.get(c.confidence, 99),
                c.case_name,
            ),
        )
