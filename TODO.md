# Frontend Impact Analyzer TODO

这个文档用于记录这个 skill 的后续研发工作，默认按优先级和阶段推进。

## 当前目标

- 把这个项目从“有主流程的雏形”推进到“对 Codex / Claude Code 这类 agent 可稳定调用的 skill”。
- 优先提升分析准确性、可验证性、可解释性，而不是继续堆描述性文档。
- 保持证据驱动、保守结论、JSON-first 的设计原则。

## 核心原则

- [ ] 结论必须优先来自真实 trace、route 绑定、AST 证据，而不是泛化猜测。
- [ ] shared component 变更不能默认扩散到全站，除非有实际 trace 支撑。
- [ ] 无法确定时保留 unresolved / low-confidence，不要过度自信。
- [ ] 输出必须稳定、结构化、便于其他 agent 继续消费。
- [ ] 最终产物是按排序输出的用例 JSON 数组，不负责执行用例。
- [ ] 每次增强都尽量配对应测试和 fixture，避免回归。

## Phase 1: 建立可验证基线

目标：先让 skill 的能力“可测、可回归、可对比”。

- [x] 新增 `tests/` 目录。
- [x] 新增 `fixtures/` 目录，放置最小 React/Vite/React Router 示例工程。
- [x] 为 `diff_parser.py` 增加单元测试。
- [x] 为 `ast_analyzer.py` 增加单元测试。
- [x] 为 `project_scanner.py` 增加单元测试。
- [x] 为 `impact_engine.py` 增加单元测试。
- [x] 为 `case_builder.py` 增加单元测试。
- [x] 增加 integration fixture，覆盖从 diff 到 result JSON 的完整链路。
- [x] 增加 snapshot 测试，固定 `impact-analysis-result.json` 输出形状。
- [x] 增加至少一组 `impact-analysis-state.json` 校验，确认 trace / unresolved / sharedRisks 的结构稳定。

### Phase 1 推荐覆盖场景

- [ ] direct page change
- [ ] business component used by one page
- [ ] shared component used by multiple pages
- [ ] hook used by multiple business components
- [ ] store used across pages
- [ ] route object with `children`
- [ ] lazy import route
- [ ] tsconfig alias import
- [ ] barrel export page/component path
- [ ] api layer request parameter change
- [ ] table columns change
- [ ] form validation change
- [ ] modal interaction change
- [ ] permission visibility change
- [ ] upload flow component change

## Phase 2: 强化 ProjectScanner 精度

目标：优先解决当前影响 page / route 识别准确率的几个关键瓶颈。

### 2.1 tsconfig alias resolution

- [x] 支持根 `tsconfig.json` 之外的 `extends`。
- [x] 支持多层 tsconfig 合并。
- [x] 支持 monorepo root + package tsconfig。
- [x] 支持一个 alias 对应多个 target path。
- [ ] 支持 wildcard edge cases。
- [x] 为 alias 解析失败增加更明确的诊断信息。

### 2.2 barrel export resolution

- [x] 支持 multi-hop barrel chain。
- [x] 支持 `export * from './x'` 多层追踪。
- [x] 支持 `export { A } from './x'` 的符号映射。
- [x] 增加循环引用保护。
- [x] 在 state 中保留 barrel resolution 证据，便于后续解释。

### 2.3 nested route parsing

- [x] 从当前启发式 path flatten 升级为真实 `children` 递归展开。
- [x] 支持 parent/child path 拼接。
- [x] 支持 layout route / wrapper route 的基础识别。
- [x] 支持 lazy route 和 route page binding 联动。
- [x] 为 route 无法绑定 page 的情况补充诊断信息。

## Phase 3: 从文件级 tracing 升级到符号级 tracing

目标：减少误报，这是长期精度提升里最关键的一步。

- [x] 明确 diff 中变更的 exported symbol。
- [x] 识别 importer 实际使用了哪些 symbol，而不是仅仅 import 了文件。
- [x] 在 impact trace 中区分 file-level trace 和 symbol-level trace。
- [x] 避免“一个 shared file 被改动，所有 import 它的页面都被高置信度命中”。
- [x] 为 `PageImpact` 增加更细的 evidence 字段，记录具体命中的 symbol。
- [x] 为 symbol-level tracing 增加专门 fixture 和回归测试。

## Phase 4: 增强 API 变更理解

目标：让这个 skill 更接近 QA 真正关心的业务风险。

- [x] 增加 request field add/remove/rename 检测。
- [x] 增加 response field add/remove/rename 检测。
- [x] 增加 enum/value change 检测。
- [x] 增加 pagination/query parameter shape change 检测。
- [x] 增加 detail/list schema change 检测。
- [x] 把 API 字段级变化映射到更具体的测试 case 模板。

## Phase 5: 强化 case generation 的业务表达

目标：让结果更像“可执行测试建议”，而不是泛泛的 smoke case。

- [ ] 在现有模板上增加更细粒度语义映射。
- [ ] 支持 create/edit/list/detail/delete 分组。
- [ ] 支持 role-based case variant。
- [ ] 支持模块级术语定制。
- [ ] 优化 case 去重策略，减少内容重复但保留必要差异。
- [ ] 补充 `impactReason` 的业务化表达，同时保留技术证据。

## Phase 6: 强化 skill 作为 agent 工具的可用性

目标：让 Codex / Claude Code 这类调用方更容易稳定集成。

- [ ] 明确输入输出契约。
- [ ] 为最终输出补充 JSON schema。
- [ ] 为 state 输出补充 JSON schema。
- [ ] 明确成功、部分成功、失败、低置信度的状态表达。
- [ ] 在 `SKILL.md` 中补充推荐调用方式和失败处理约定。
- [ ] 在结果中增加更清晰的 unresolved / sharedRisks 说明字段。
- [ ] 评估是否需要 machine-readable diagnostics 字段，方便 agent 二次处理。

## 近期推荐执行顺序

- [x] 先完成 Phase 1 的 fixtures + tests。
- [x] 然后集中推进 Phase 2 的 alias / barrel / nested route。
- [x] 接着推进 Phase 3 的 symbol-level tracing。
- [x] 再做 Phase 4 的 API field diff。
- [ ] 最后增强 Phase 5 和 Phase 6。

## 第一批最值得立刻开始的具体任务

- [x] 新建 `tests/test_diff_parser.py`
- [x] 新建 `tests/test_ast_analyzer.py`
- [x] 新建 `tests/test_project_scanner.py`
- [x] 新建 `tests/test_impact_engine.py`
- [x] 新建 `tests/test_case_builder.py`
- [x] 新建 `fixtures/sample_app/`
- [x] 新建 `fixtures/diffs/`
- [x] 准备第一组 snapshot expected JSON
- [x] 为 `load_tsconfig_aliases` 补 `extends` 支持
- [x] 为 `ProjectScanner` 补多跳 barrel resolution
- [x] 为 route parsing 补真正的 children 递归展开

## Done Log

用于后续记录已经完成的事项。

- [x] 使用 `uv` 管理项目依赖，新增 `pyproject.toml`
- [x] 生成 `uv.lock`
- [x] 更新 `SKILL.md` 中的运行方式
- [x] 将最终输出契约切换为按排序输出的用例 JSON 数组
- [x] 建立 Phase 1 的测试、fixture、snapshot 基线
- [x] 完成 Phase 2 第一轮：alias extends、多目标 alias、multi-hop barrel、递归 nested routes
- [x] 完成 Phase 2 第二轮：lazy route 绑定、scanner diagnostics、barrel evidence state
- [x] 完成 Phase 3 第一轮：symbol-level first-hop filtering、format-only diff skip、matched symbol evidence
- [x] 完成 Phase 4 第一轮：API 字段级 diff 检测与用例模板映射
