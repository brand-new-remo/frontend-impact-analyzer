# 前端影响分析器技能文档

<cite>
**本文档引用的文件**
- [SKILL.md](file://SKILL.md)
- [AGENTS.md](file://AGENTS.md)
- [HANDOFF.md](file://internal/HANDOFF.md)
- [pyproject.toml](file://pyproject.toml)
- [front_end_impact_analyzer.py](file://scripts/front_end_impact_analyzer.py)
- [models.py](file://scripts/analyzer/models.py)
- [diff_parser.py](file://scripts/analyzer/diff_parser.py)
- [project_scanner.py](file://scripts/analyzer/project_scanner.py)
- [impact_engine.py](file://scripts/analyzer/impact_engine.py)
- [cluster_builder.py](file://scripts/analyzer/cluster_builder.py)
- [common.py](file://scripts/analyzer/common.py)
- [analysis-result.schema.json](file://schemas/analysis-result.schema.json)
- [impact-rules.md](file://references/impact-rules.md)
- [route-conventions.md](file://references/route-conventions.md)
</cite>

## 目录
1. [项目概述](#项目概述)
2. [核心工作流程](#核心工作流程)
3. [系统架构](#系统架构)
4. [核心组件分析](#核心组件分析)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考虑](#性能考虑)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)

## 项目概述

前端影响分析器是一个专为React、React Router和Vite项目设计的智能分析工具，能够将前端变更影响转化为可执行的QA测试案例。该工具通过静态分析技术，从代码变更中提取证据，并将其转换为面向业务的功能性影响分析。

### 主要特性

- **AST驱动的代码理解**：使用tree-sitter解析TypeScript/JavaScript代码
- **导入/反向导入依赖追踪**：构建完整的模块依赖图
- **路由页面绑定**：支持嵌套路由和懒加载路由
- **别名解析**：支持tsconfig路径别名和扩展
- **桶装导出处理**：支持多层导出重定向
- **过程状态持久化**：确定性的JSON输出格式

## 核心工作流程

### 1. 环境检查和配置
```mermaid
flowchart TD
A["启动技能"] --> B["检查uv环境"]
B --> C{"uv是否安装?"}
C --> |否| D["停止并提示安装uv"]
C --> |是| E["检查Python版本"]
E --> F{"Python >= 3.12?"}
F --> |否| G["停止并提示升级Python"]
F --> |是| H["检查tree-sitter依赖"]
H --> I["加载配置文件"]
I --> J["执行预检报告"]
```

### 2. 变更检测和分类
```mermaid
sequenceDiagram
participant U as 用户
participant A as 分析器
participant D as 差分解析器
participant C as 噪声分类器
participant G as 全局分类器
U->>A : 提交git diff
A->>D : 解析差分内容
D-->>A : 变更文件列表
A->>C : 分类非逻辑噪声
C-->>A : 噪声分类结果
A->>G : 识别全局变更
G-->>A : 全局分类结果
```

### 3. 项目扫描和依赖分析
```mermaid
graph TB
subgraph "项目扫描阶段"
A[AST解析] --> B[导入关系提取]
B --> C[反向导入图构建]
C --> D[页面识别]
D --> E[路由信息提取]
E --> F[别名解析]
F --> G[桶装导出处理]
end
```

### 4. 影响追踪和聚类
```mermaid
flowchart LR
A["变更种子"] --> B["页面追踪"]
B --> C["影响类型判定"]
C --> D["置信度评估"]
D --> E["聚类算法"]
E --> F["深度分析集群"]
F --> G["浅层分析集群"]
```

## 系统架构

### 整体架构设计
```mermaid
graph TB
subgraph "用户界面层"
U[Claude Code]
T[Test工程师]
end
subgraph "分析引擎层"
FEIA[前端影响分析器]
ORCH[协调器]
MODELS[模型层]
end
subgraph "分析组件层"
DP[差分解析器]
PS[项目扫描器]
IA[影响分析器]
CB[聚类构建器]
CC[上下文收集器]
end
subgraph "存储层"
STATE[分析状态]
ARTIFACTS[运行工件]
SCHEMA[JSON模式]
end
U --> FEIA
T --> FEIA
FEIA --> ORCH
ORCH --> MODELS
ORCH --> DP
ORCH --> PS
ORCH --> IA
ORCH --> CB
ORCH --> CC
ORCH --> STATE
ORCH --> ARTIFACTS
ORCH --> SCHEMA
```

### 数据流架构
```mermaid
flowchart TD
A["Git Diff输入"] --> B["差分解析"]
B --> C["文件分类"]
C --> D["项目扫描"]
D --> E["依赖分析"]
E --> F["影响追踪"]
F --> G["聚类构建"]
G --> H["上下文收集"]
H --> I["Claude分析"]
I --> J["结果合并"]
J --> K["最终输出"]
```

## 核心组件分析

### 分析器引擎 (FrontendImpactAnalysisEngine)
分析器引擎是整个系统的协调中心，负责管理完整的分析流程：

```mermaid
classDiagram
class FrontendImpactAnalysisEngine {
+project_root : Path
+diff_text : str
+requirement_text : str
+config : dict
+manifest : dict
+preflight_report : dict
+state : AnalysisState
+recorder : ProcessRecorder
+store : StateStore
+run() AnalysisState
+write_run_artifacts(run_dir, state) void
+_build_analysis_package(clusters, coverage, document_index) dict
}
class AnalysisState {
+meta : Dict
+input : Dict
+parsedDiff : Dict
+codeGraph : Dict
+codeImpact : Dict
+candidateImpact : Dict
+businessImpact : Dict
+workflow : Dict
+output : Any
+processLogs : List[Dict]
+to_dict() Dict
}
class ProcessRecorder {
+state : AnalysisState
+log(step, status, message) void
}
class StateStore {
+state : AnalysisState
+set_diff(commit_types, changed_files) void
+set_graph(imports, reverse_imports, pages, routes, ast_facts) void
+set_file_classifications(changed_files) void
}
FrontendImpactAnalysisEngine --> AnalysisState
FrontendImpactAnalysisEngine --> ProcessRecorder
FrontendImpactAnalysisEngine --> StateStore
```

**章节来源**
- [front_end_impact_analyzer.py:38-187](file://scripts/front_end_impact_analyzer.py#L38-L187)
- [models.py:116-169](file://scripts/analyzer/models.py#L116-L169)

### 差分解析器 (GitDiffParser)
差分解析器负责解析git diff输出，提取语义信息和变更类型：

```mermaid
classDiagram
class GitDiffParser {
+DIFF_FILE_RE : Pattern
+NEW_FILE_RE : Pattern
+DELETE_FILE_RE : Pattern
+HUNK_RE : Pattern
+COMMIT_TYPE_RE : Pattern
+SYMBOL_PATTERNS : List[Pattern]
+SEMANTIC_PATTERNS : Dict[str, List[Pattern]]
+FIELD_NAME_PATTERNS : List[Pattern]
+ENUM_VALUE_PATTERN : Pattern
+REQUEST_HINT_RE : Pattern
+RESPONSE_HINT_RE : Pattern
+parse() Tuple[List[str], List[ChangedFile]]
+_finalize_changed_file(current, added_content, removed_content) void
+_analyze_api_changes(file_path, added_lines, removed_lines) List[dict]
+_semantic_tags_from_api_changes(api_changes) List[str]
}
class ChangedFile {
+path : str
+change_type : str
+added_lines : int
+removed_lines : int
+symbols : List[str]
+semantic_tags : List[str]
+api_changes : List[Dict[str, str]]
+file_type : str
+module_guess : str
+is_format_only : bool
+noise_classification : Dict
+global_classification : Dict
}
GitDiffParser --> ChangedFile
```

**章节来源**
- [diff_parser.py:11-302](file://scripts/analyzer/diff_parser.py#L11-L302)
- [models.py:27-40](file://scripts/analyzer/models.py#L27-L40)

### 项目扫描器 (ProjectScanner)
项目扫描器执行全面的代码分析，构建依赖图和路由信息：

```mermaid
classDiagram
class ProjectScanner {
+project_root : Path
+src_root : Path
+ast : TsAstAnalyzer
+aliases : Dict[str, List[str]]
+scan(changed_file_paths) Tuple
+_collect_source_files() List[Path]
+_resolve_imports(current_dir, raw_target) List[Path]
+_is_page(rel_file, facts) bool
+_is_page_candidate(rel_file) bool
+_is_route_file(rel_file) bool
+_build_analysis_set(changed_file_paths, reverse_imports, candidate_pages, route_files, imports) set
+_extract_route_records_from_tree(file_path, source_bytes, tree) List[Dict]
+_expand_route_records(rel_file, route_records, imports, ast_facts, pages, diagnostics) List[RouteInfo]
}
class RouteInfo {
+route_path : Optional[str]
+source_file : str
+linked_page : Optional[str]
+route_component : Optional[str]
+parent_route : Optional[str]
+confidence : str
+route_comment : str
+display_name : str
+display_name_source : str
}
ProjectScanner --> RouteInfo
```

**章节来源**
- [project_scanner.py:13-509](file://scripts/analyzer/project_scanner.py#L13-L509)
- [models.py:43-53](file://scripts/analyzer/models.py#L43-L53)

### 影响分析器 (ImpactAnalyzer)
影响分析器负责将代码变更追踪到具体的页面和功能：

```mermaid
classDiagram
class ImpactAnalyzer {
+imports : Dict[str, List[str]]
+reverse_imports : Dict[str, List[str]]
+pages : Set[str]
+routes : List[RouteInfo]
+ast_facts : Dict[str, Dict]
+route_map : Dict[str, List[str]]
+analyze_file(cf) Tuple[List[PageImpact], Optional[Dict]]
+_build_page_direct_impacts(cf) List[PageImpact]
+_trace_to_pages(start_file, changed_symbols) List[Tuple[List[str], List[str]]]
+_symbols_for_parent(current_file, parent_file, active_symbols, strict_symbols) Optional[Tuple[List[str], bool]]
+_impact_type(file_type) str
+_confidence(file_type, trace, semantics) str
+_reason(file_type, trace, semantics, matched_symbols) str
}
class PageImpact {
+changed_file : str
+page_file : str
+route_path : Optional[str]
+module_name : str
+trace : List[str]
+impact_type : str
+confidence : str
+impact_reason : str
+semantic_tags : List[str]
+matched_symbols : List[str]
+api_changes : List[Dict[str, str]]
}
ImpactAnalyzer --> PageImpact
```

**章节来源**
- [impact_engine.py:10-188](file://scripts/analyzer/impact_engine.py#L10-L188)
- [models.py:78-90](file://scripts/analyzer/models.py#L78-L90)

### 聚类构建器 (ChangeClusterBuilder)
聚类构建器将相关的变更组合成分析集群：

```mermaid
classDiagram
class ChangeClusterBuilder {
+diff_text : str
+diff_previews : Dict[str, Dict]
+build_diff_index(changed_files) Dict
+build_file_impact_seeds(changed_files, impacts, unresolved) Dict
+build_clusters(seeds_data, max_deep_clusters) Dict
+build_coverage(diff_index, clusters_data, diagnostics) Dict
+_analysis_bucket(cf) str
+_seed_confidence(cf, impacts) str
+_cluster_confidence(kind, seeds) str
+_cluster_title(kind, key, pages, seeds) str
+_cluster_reason(kind, pages) str
+_extract_diff_previews(diff_text) Dict
}
```

**章节来源**
- [cluster_builder.py:11-312](file://scripts/analyzer/cluster_builder.py#L11-L312)

## 详细组件分析

### 配置管理系统
配置系统提供了灵活的项目定制能力：

```mermaid
flowchart TD
A["默认配置文件"] --> B["路径配置"]
A --> C["差异过滤规则"]
A --> D["分析行为控制"]
B --> B1["repoWikiDir"]
B --> B2["projectProfileFile"]
B --> B3["requirementsDir"]
B --> B4["specsDir"]
B --> B5["diffDir"]
B --> B6["outputDir"]
C --> C1["includePaths"]
C --> C2["ignoreDirs"]
C --> C3["ignoreFiles"]
C --> C4["ignoreGlobs"]
D --> D1["requireRepoWiki"]
D --> D2["requireRequirements"]
D --> D3["requireSpecs"]
D --> D4["maxClusterContextChars"]
D --> D5["phasedExecutionThreshold"]
```

### 运行工件管理
每次分析都会生成完整的运行工件集：

```mermaid
graph TB
subgraph "运行目录结构"
A["00-run-manifest.json"] --> B["运行清单"]
C["01-preflight-report.json"] --> D["预检报告"]
E["02-document-index.json"] --> F["文档索引"]
G["03-diff-index.json"] --> H["差异索引"]
I["04-file-impact-seeds.json"] --> J["文件影响种子"]
K["05-change-clusters.json"] --> L["变更聚类"]
M["06-cluster-analysis-tasks.md"] --> N["聚类分析任务"]
O["cluster-context/"] --> P["聚类上下文文件"]
Q["cluster-analysis/"] --> R["聚类分析结果"]
S["90-coverage-report.json"] --> T["覆盖率报告"]
U["98-analysis-state.json"] --> V["分析状态"]
W["99-final-result.json"] --> X["最终结果"]
Y["99-merged-result.json"] --> Z["合并结果"]
end
```

### Claude代理集成
系统支持多个Claude Code代理模板：

```mermaid
graph LR
subgraph "Claude代理"
A[change-intent-judge] --> B["精确用户可见变更判断"]
C[evidence-checker] --> D["证据验证和置信度评估"]
E[case-writer] --> F["特定QA用例编写"]
G[case-refiner] --> H["最终用例精炼"]
end
subgraph "分析流程"
I["聚类上下文"] --> A
A --> J["变更意图"]
J --> C
C --> K["验证用例"]
K --> E
E --> L["具体用例"]
L --> M["合并阶段"]
M --> G
G --> N["精炼用例"]
end
```

## 依赖关系分析

### 外部依赖
```mermaid
graph TB
subgraph "核心依赖"
A[tree-sitter] --> B[语法树解析]
C[tree-sitter-typescript] --> D[TypeScript解析]
end
subgraph "开发依赖"
E[pytest] --> F[测试框架]
end
subgraph "运行时依赖"
G[uv] --> H[包管理器]
I[Python 3.12+] --> J[运行环境]
end
```

### 内部模块依赖
```mermaid
graph TD
A[front_end_impact_analyzer.py] --> B[models.py]
A --> C[diff_parser.py]
A --> D[project_scanner.py]
A --> E[impact_engine.py]
A --> F[cluster_builder.py]
A --> G[common.py]
C --> H[noise_classifier.py]
D --> I[ast_analyzer.py]
E --> J[source_classifier.py]
F --> K[result_merger.py]
```

**章节来源**
- [pyproject.toml:1-20](file://pyproject.toml#L1-L20)

## 性能考虑

### 大型项目优化策略
1. **分阶段执行**：对于大型diff（超过1000行），自动启用分阶段执行
2. **增量分析**：仅对受变更影响的文件进行完整AST分析
3. **内存优化**：使用轻量级导入扫描作为第一阶段
4. **批处理上下文**：聚类上下文收集支持批处理以减少I/O开销

### 缓存机制
- **树缓存**：在第一阶段解析的AST树在第二阶段复用
- **路径规范化**：统一路径格式避免重复计算
- **去重机制**：确保分析结果的唯一性和一致性

## 故障排除指南

### 常见问题诊断
```mermaid
flowchart TD
A["分析失败"] --> B{"错误类型"}
B --> |环境问题| C["检查uv安装"]
B --> |配置问题| D["验证配置文件"]
B --> |依赖问题| E["检查tree-sitter安装"]
B --> |内存问题| F["启用分阶段执行"]
C --> G["重新安装uv"]
D --> H["修正配置项"]
E --> I["重新安装tree-sitter"]
F --> J["调整phasedExecutionThreshold"]
```

### 错误恢复策略
1. **预检失败**：根据预检报告中的阻塞动作进行修复
2. **未解析导入**：检查tsconfig别名配置和文件路径
3. **路由绑定失败**：验证路由定义和页面组件匹配
4. **聚类分析缺失**：检查聚类上下文文件生成情况

**章节来源**
- [HANDOFF.md:104-114](file://internal/HANDOFF.md#L104-L114)

## 结论

前端影响分析器提供了一个完整的工程化解决方案，将静态分析与人工智能相结合，实现了从代码变更到可执行测试用例的自动化转换。其核心优势包括：

1. **确定性输出**：严格的JSON模式保证了输出的一致性和可验证性
2. **渐进式分析**：支持分阶段执行，适应不同规模的项目需求
3. **证据驱动**：每个结论都有相应的代码和文档证据支撑
4. **可扩展性**：模块化的架构设计便于功能扩展和定制

该工具特别适合处理大型PR和发布版本的变更影响分析，能够显著提高QA团队的工作效率和质量保证水平。