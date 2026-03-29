

# Frontend Impact Analyzer - Project Handoff for Codex

## 1. Project goal

This project is a reusable Skill for analyzing **front-end change impact** in a **React + React Router + Vite** codebase.

Its purpose is to take:
- requirement/design text for the current change
- git diff / PR diff content
- the local project source tree

and produce:
- impacted modules
- impacted pages
- impacted routes
- impacted functional areas
- structured JSON test cases for QA / testing

The core product idea is:

> Use static analysis to find evidence, then convert technical impact into testable business-facing functional impact.

This is intentionally **not** a pure prompt-only solution.
It is meant to be an **engineering-style analyzer** with:
- AST-based code understanding
- import / reverse-import dependency tracing
- route-page binding
- alias resolution
- barrel export handling
- process/state persistence
- deterministic JSON output

---

## 2. What has already been designed

The current design direction is already established and should be preserved unless there is a strong reason to change it.

### High-level workflow

1. Read requirement text.
2. Read git diff.
3. Parse changed files from diff.
4. Extract semantic signals from diff.
5. Scan project source files.
6. Build import graph and reverse import graph.
7. Resolve aliases from tsconfig.
8. Resolve barrel exports.
9. Parse route definitions, including nested routes and lazy imports.
10. Trace changed files upward to top-level pages.
11. Bind pages to routes where possible.
12. Infer impacted modules/pages/functions.
13. Generate structured JSON test cases.
14. Save both state and final result.

### Guiding principle

The analyzer should always prefer:
- direct page evidence
- direct route evidence
- real import traces

over broad guesses.

It must **not** casually say “the whole system is affected” just because a shared component changed.

---

## 3. Intended user scenario

Primary user:
- software test development engineer / QA engineer

Typical scenario:
- a developer provides a requirement implementation note
- a PR or commit provides git diff content
- the analyzer determines which pages/modules/functions are likely affected
- the analyzer outputs JSON test cases by module

Expected output shape:
- module-oriented
- page-aware
- evidence-based
- structured for follow-up automation or direct import into test systems

---

## 4. Skill-level scope

This project is a **Skill bundle**, not just a script.

The skill is intended to be used by another agent / ChatGPT / Codex-like tool to:
- run the script
- inspect generated JSON
- answer with final impact analysis

The Skill currently contains or should contain:
- `SKILL.md`
- `agents/openai.yaml`
- `scripts/front_end_impact_analyzer.py`
- `scripts/analyzer/*.py`
- `references/*.md`

### Current intended file structure

```text
frontend-impact-analyzer/
├── AGENTS.md
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── impact-rules.md
│   ├── project-conventions.md
│   └── route-conventions.md
└── scripts/
    ├── front_end_impact_analyzer.py
    └── analyzer/
        ├── __init__.py
        ├── models.py
        ├── common.py
        ├── diff_parser.py
        ├── source_classifier.py
        ├── ast_analyzer.py
        ├── project_scanner.py
        ├── impact_engine.py
        └── case_builder.py
```

If anything is missing from the working directory, Codex should reconstruct it from this design document.

---

## 5. What the analyzer is expected to support

### 5.1 Framework / project assumptions

Primary target:
- React
- React Router
- Vite
- TypeScript or JavaScript

Common file types:
- `.ts`
- `.tsx`
- `.js`
- `.jsx`

Common code locations:
- `src/pages`
- `src/views`
- `src/router`
- `src/routes`
- `src/components`
- `src/features`
- `src/hooks`
- `src/store`
- `src/context`
- `src/api`
- `src/services`
- `src/utils`
- `src/constants`
- `src/schema`

### 5.2 Import styles to support

The analyzer is expected to understand:
- relative imports
- `@/` imports
- `tsconfig.json` path alias imports
- lazy imports
- barrel exports

### 5.3 Route styles to support

The analyzer should handle:
- route object arrays
- `path`
- `element`
- `component`
- `children`
- `lazy(() => import(...))`
- nested route path concatenation

---

## 6. Core architecture

The project has already been conceptually split into modules. This modular design should remain.

### 6.1 `models.py`

Responsibilities:
- define dataclasses / state models
- define logs / process records
- define changed file model
- define route info model
- define AST facts model
- define page impact model
- define test case model
- define overall analysis state model

Expected kinds of models:
- `ProcessLog`
- `ChangedFile`
- `RouteInfo`
- `FileAstFacts`
- `PageImpact`
- `TestCase`
- `AnalysisState`

This layer should be pure data structures.

---

### 6.2 `common.py`

Responsibilities:
- path normalization
- relative path conversion
- file reading helpers
- dedupe helpers
- module name inference
- title formatting from filenames
- confidence/priority mapping
- tsconfig alias parsing helpers
- general reusable utility logic

Important future extension points:
- robust tsconfig parser
- alias inheritance / extends support
- OS-independent path normalization

---

### 6.3 `diff_parser.py`

Responsibilities:
- parse git diff text
- identify changed files
- classify change type:
  - modified
  - added
  - deleted
- count added/removed lines
- extract symbols from changed lines
- extract semantic tags from changed lines
- infer commit types from messages if present

Important semantic tags currently intended in the design:
- button
- modal
- form
- table
- route
- permission
- api
- state
- navigation
- validation
- list-query
- submit
- columns
- detail
- loading
- disabled-state
- export

Future enhancement directions:
- stronger diff hunk parsing
- field-level API diff detection
- enum/value change detection
- request/response contract change detection

---

### 6.4 `source_classifier.py`

Responsibilities:
- classify source file role from path and filename

Expected file types:
- `page`
- `route`
- `api`
- `store`
- `hook`
- `shared-component`
- `business-component`
- `utils`
- `config-or-schema`
- `style`
- `non-source`
- `unknown`

This classification is very important because confidence and impact type depend heavily on it.

---

### 6.5 `ast_analyzer.py`

Responsibilities:
- use `tree_sitter` + `tree_sitter_typescript`
- parse `.ts/.tsx/.js/.jsx`
- extract AST-level facts from files

Expected extracted data:
- imports
- exports
- component names
- hook names
- JSX tags
- JSX props
- route paths
- route components
- lazy imports
- API calls
- derived semantic tags

The AST analyzer is the heart of the “not just regex” improvement.

Current intended dependency:
- `tree_sitter`
- `tree_sitter_typescript`

Expected parser split:
- TS parser for `.ts/.js`
- TSX parser for `.tsx/.jsx`

Future enhancement directions:
- stronger call target extraction
- symbol-level dependency extraction
- prop flow extraction
- state/store usage extraction
- permission hook usage extraction

---

### 6.6 `project_scanner.py`

Responsibilities:
- scan project files
- resolve imports
- build import graph
- build reverse import graph
- support alias resolution
- support barrel exports
- support route-page linking
- support lazy route linking
- expand nested routes

This module is responsible for converting many file-local AST facts into project-level structure.

#### Key expected capabilities

##### A. Source collection
- recursively scan the source tree
- ignore common dirs like `node_modules`, `.git`, `dist`, `build`, etc.

##### B. Import resolution
Support resolution for:
- relative paths
- `@/` root paths
- tsconfig path aliases
- file candidates:
  - direct file
  - `.ts`
  - `.tsx`
  - `.js`
  - `.jsx`
  - `index.ts`
  - `index.tsx`
  - `index.js`
  - `index.jsx`

##### C. Barrel export handling
Handle cases such as:
- `export * from './x'`
- `export { A } from './x'`
- index-layer re-export files

Expected behavior:
- if a route or component imports a barrel file, scanner should be able to continue tracing through the barrel target
- if a page is only reachable through a barrel export path, that relationship should still be traceable

##### D. Route binding
Support route-to-page inference via:
1. direct imported page file
2. lazy imported page file
3. component-name match between route component and page exports/components
4. nested children route concatenation

This route support is one of the most important precision improvements.

Future enhancement directions:
- route modules split across multiple files
- plugin-generated routes
- file-based routes
- route wrappers/layouts

---

### 6.7 `impact_engine.py`

Responsibilities:
- trace changed files upward to pages
- combine diff semantics + AST semantics
- assign impact type
- assign confidence
- produce page impacts
- record unresolved files
- identify shared risks

Expected behavior:
- page change => direct, high confidence
- route change => direct, high confidence if bound to page
- api/hook/store/business-component => direct if traced to page
- shared-component => indirect or medium/low depending on evidence
- utils/config/style => low confidence unless stronger evidence exists

This module must be conservative.
It should not over-expand impact when evidence is weak.

Important principle:
- **trace first, then conclude**

Future enhancement directions:
- symbol-level trace instead of file-level trace
- more nuanced confidence scoring
- route-layout-aware tracing
- cross-module shared store impact clustering

---

### 6.8 `case_builder.py`

Responsibilities:
- convert page impacts into structured test cases
- generate module-oriented JSON output
- map semantics to test templates

Expected semantic-to-case mapping includes:
- base page regression
- button entry and click behavior
- modal open/close/submit
- form render/validation/submit
- table columns/selection/pagination/sort/filter
- api request/render/error handling
- query/filter/pagination/sort scenarios
- detail/echo scenarios
- delete flow
- permission checks
- navigation / route entry / refresh / back
- upload flow
- disabled/readOnly state

This layer should remain template-based and deterministic.

Future enhancement directions:
- project-specific case templates
- per-module domain language
- test platform export adapters
- dedupe smarter by semantics and route/page identity

---

### 6.9 `front_end_impact_analyzer.py`

Responsibilities:
- CLI entry point
- orchestrate all modules
- produce final state file
- produce final result file

Expected pipeline:
1. parse CLI args
2. read diff and requirement files
3. parse diff
4. classify changed files
5. scan project with AST
6. trace impact
7. build cases
8. write state JSON
9. write result JSON

This file should stay thin and orchestration-focused.

---

## 7. State design and process management

This project is intended to be **state-driven**, not just print-and-forget.

### State layers

#### Input
- requirementText
- gitDiffText

#### Parsed diff state
- commit types
- changed files
- change type
- semantic tags
- symbols

#### Code graph state
- imports
- reverseImports
- pages
- routes
- astFacts

#### Code impact state
- file classifications
- page impacts
- unresolved files
- shared risks

#### Business impact state
- affected modules
- affected pages
- affected functions

#### Output state
- summary
- cases

#### Process logs
Every major phase should log:
- step name
- status
- message
- timestamp

This is important for:
- debugging
- explaining how the analyzer arrived at results
- allowing future agent tools to inspect intermediate evidence

---

## 8. Why AST was chosen

Earlier versions were regex-heavy and weaker.
That approach was intentionally upgraded.

AST is preferred because it is more reliable for:
- import extraction
- JSX tag detection
- route object extraction
- lazy import detection
- API call identification
- component/hook naming

The project direction is now clearly:

> Use AST for structure, use rules for interpretation.

That design should remain the baseline.

---

## 9. Why modularization was chosen

The code was intentionally moved toward multi-module organization because the analyzer is expected to continue growing.

Main reasons:
- easier debugging
- easier replacement of components
- easier project-specific customization
- easier CI integration later
- easier to test scanner/impact/case logic independently

Codex should preserve this modular architecture rather than collapsing everything into one script.

---

## 10. Expected output format

The final output is expected to be strict JSON.

### Summary
Should include at least:
- `affectedModules`
- `affectedPages`
- `affectedFunctions`
- `riskLevel`

### Cases
Each case should include:
- `moduleName`
- `pageName`
- `caseName`
- `preconditions`
- `testSteps`
- `expectedResults`
- `impactType`
- `priority`
- `impactReason`
- `relatedFiles`
- `confidence`

The analyzer should never output vague prose when structured JSON is expected.

---

## 11. Current known limitations

These limitations are already known and should be treated as improvement areas, not surprises.

### 11.1 Import / symbol precision
Current direction is still mainly **file-level tracing**, not full **symbol-level tracing**.

That means:
- if a file exports many things, the analyzer may over-associate at file granularity
- future work should improve symbol-level dependency reasoning

### 11.2 Route parsing is improved but not perfect
Supported better than before, but still limited in complex scenarios like:
- very dynamic route factories
- wrapper-generated routes
- plugin-generated routes
- route config split across transformation layers

### 11.3 API analysis is still semantic rather than contract-aware
The project knows “API-like change happened,” but not yet fully:
- request field rename
- response field removal
- schema diff
- enum value change

### 11.4 Barrel resolution can still be incomplete
Especially when:
- multiple barrel layers chain together
- export names are renamed heavily
- barrel graph becomes cyclic or indirect

### 11.5 tsconfig alias handling may need more work
Especially for:
- multiple tsconfig layers
- `extends`
- monorepo path mappings
- custom workspace conventions

---

## 12. Next recommended development priorities

These are the most valuable next steps for Codex.

### Priority 1: strengthen tsconfig alias resolution
Support:
- `extends`
- monorepo root tsconfig + package tsconfig
- multiple alias targets
- wildcard mapping edge cases

### Priority 2: strengthen barrel export resolution
Support:
- multi-hop barrel chains
- re-exported symbol mapping
- better cycle protection

### Priority 3: strengthen nested route parsing
Support:
- full recursive children flattening
- parent/child path joining
- layout-aware route binding
- route wrappers

### Priority 4: add field-level API diff analysis
This is one of the highest-value precision upgrades.

Target capabilities:
- request field add/remove/rename detection
- response field add/remove/rename detection
- enum value change detection
- pagination parameter shape changes
- detail/list schema changes

### Priority 5: move from file-level to symbol-level tracing
This is the long-term precision milestone.

Target capabilities:
- identify which exported symbol changed
- identify which importer actually uses that symbol
- avoid marking an entire page as impacted if it imports the file but not the changed symbol

### Priority 6: richer case generation rules
Add:
- module-specific templates
- role-based test case variants
- create/edit/list/detail/delete grouped cases
- project-specific language adaptation

---

## 13. Suggested future engineering tasks for Codex

If continuing this project, a good concrete backlog would be:

1. Reconstruct or verify all script modules exist.
2. Add unit tests for:
   - diff parsing
   - alias resolution
   - barrel resolution
   - route parsing
   - impact tracing
   - case generation
3. Add a small sample fixture project for integration testing.
4. Add a sample diff fixture set.
5. Add snapshot tests for expected JSON output.
6. Add a CI command that runs the analyzer against fixtures.
7. Add better error handling / diagnostics when a route or alias cannot be resolved.
8. Add symbol-level analysis research spike.
9. Add field-level API diff research spike.
10. Add test platform adapters if needed later.

---

## 14. Suggested test strategy for the analyzer itself

Codex should not rely only on manual testing.

### Recommended automated tests

#### A. Diff parser tests
Input:
- small diffs with known files and semantics
Expected:
- correct changed files
- correct symbols
- correct semantic tags

#### B. AST analyzer tests
Input:
- TS/TSX sample files
Expected:
- correct imports
- correct JSX tags
- correct route paths
- correct lazy imports
- correct API calls

#### C. Project scanner tests
Input:
- fixture projects with alias + barrel + lazy route
Expected:
- correct import graph
- correct reverse import graph
- correct route-page binding

#### D. Impact engine tests
Input:
- changed file + known graph
Expected:
- expected traced pages
- expected confidence
- expected unresolved results

#### E. Case builder tests
Input:
- impacts with known semantic tags
Expected:
- correct test case templates
- deterministic JSON shape

---

## 15. Suggested fixture project scenarios

To improve the analyzer meaningfully, Codex should probably create fixtures that cover:

1. direct page change
2. business component used by one page
3. shared component used by multiple pages
4. hook used by multiple business components
5. store used across pages
6. route object with `children`
7. lazy import route
8. tsconfig alias import
9. barrel export page/component path
10. api layer request parameter change
11. table columns change
12. form validation change
13. modal interaction change
14. permission visibility change
15. upload flow component change

---

## 16. Packaging / skill intent

This repository is expected to remain compatible with Skill packaging.

Important requirements:
- `SKILL.md` should remain concise but actionable.
- scripts should be runnable from the skill context.
- references should explain conventions, not duplicate code.
- final output should remain JSON-first.

Codex should preserve the idea that:
- scripts do deterministic analysis
- skill instructions tell the agent how to use the scripts

---

## 17. Important implementation philosophy

These are the non-obvious project rules Codex should keep in mind.

### Rule 1
Do not replace evidence-based impact tracing with broad LLM-only guessing.

### Rule 2
Do not expand impact to all pages when only a shared component changed unless traces support it.

### Rule 3
Always preserve unresolved/low-confidence states instead of overclaiming certainty.

### Rule 4
Keep the analyzer’s process inspectable through state and logs.

### Rule 5
Prefer modular code and explicit data models over giant script logic.

### Rule 6
Route binding, alias resolution, and barrel handling are core precision features, not optional extras.

### Rule 7
The analyzer should translate technical changes into testable user-facing behaviors.

---

## 18. If Codex needs to rebuild missing files

If parts of the project are missing, Codex should rebuild them using this order:

1. `scripts/analyzer/models.py`
2. `scripts/analyzer/common.py`
3. `scripts/analyzer/diff_parser.py`
4. `scripts/analyzer/source_classifier.py`
5. `scripts/analyzer/ast_analyzer.py`
6. `scripts/analyzer/project_scanner.py`
7. `scripts/analyzer/impact_engine.py`
8. `scripts/analyzer/case_builder.py`
9. `scripts/front_end_impact_analyzer.py`
10. fixture tests
11. skill references cleanup

---

## 19. Most important near-term enhancements

If there is time for only a small number of improvements, prioritize these:

1. tsconfig alias support improvement
2. barrel export multi-hop support
3. nested children route full flattening
4. API field-level diff analysis
5. symbol-level dependency tracing

That order reflects current leverage on precision.

---

## 20. Final summary for Codex

This project is a **front-end impact analysis skill + analyzer**.

Its mission is to:
- read requirement text and git diff
- inspect a React/Vite/React Router codebase
- find the top-level impacted pages/routes/modules
- infer user-visible functional impact
- output strict JSON test cases

The current design direction already strongly favors:
- AST over regex
- stateful process management
- modular architecture
- trace-based evidence
- conservative confidence handling
- structured JSON output

The next major technical frontier is:
- better alias/barrel/route resolution
- field-level API diff understanding
- symbol-level tracing

Codex should treat this file as the authoritative handoff context for continuing development.