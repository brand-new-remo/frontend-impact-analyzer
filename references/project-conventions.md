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

Extend alias handling in `scripts/analyzer/project_scanner.py` if your project uses additional alias conventions not declared in tsconfig.
