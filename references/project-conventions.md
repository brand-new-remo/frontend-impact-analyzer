# Project conventions

Recommended assumptions for this analyzer:
- Main source code lives under `src/`.
- Pages commonly live in `src/pages` or `src/views`.
- React Router route definitions may appear in `src/router`, `src/routes`, route arrays, or lazy-loaded route modules.
- The analyzer supports:
  - relative imports
  - `@/` imports
  - tsconfig path aliases
  - barrel exports (`export * from`, `export { X } from`)

Generalization rules:
- Treat any target-project profile document as a source of examples, not hard-coded rules.
- Extract reusable patterns such as page roots, route styles, alias styles, barrel usage, and API file conventions.
- Keep project-specific paths, naming quirks, and build details as supplemental heuristics unless they recur across multiple projects.
- Prefer adding configurable or evidence-based rules over baking one project's structure into the scanner.

Extend alias handling in `scripts/analyzer/project_scanner.py` if your project uses additional alias conventions not declared in tsconfig.
