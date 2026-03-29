# Route conventions

The analyzer supports these patterns:
- route object arrays with `path`, `element`, `component`, `children`
- lazy routes such as `lazy(() => import('...'))`
- nested child routes by concatenating parent and child path segments
- route-to-page binding by:
  1. direct imported page file
  2. lazy imported page file
  3. route component name matching page exports/components
