# Impact rules

Confidence guidance:
- high: changed page/route directly, or trace length is short and route/page binding is strong
- medium: business component / hook / store / api traced to concrete pages
- low: shared component, style, utils, schema, or unresolved barrel/alias indirection

Semantic to test mapping:
- button: entry visibility, click behavior, disabled state
- modal: open/close, confirm/cancel, initialization/reset
- form/validation: field render, required rules, invalid/valid submit
- table/columns: columns, row actions, selection, pagination, sorting, filtering
- api/list-query: request params, result rendering, empty/error handling
- detail: detail page and edit echo
- delete: delete confirm, success/failure feedback
- permission: role-based visibility and operability
- navigation/route: route entry, jump, refresh, browser back, nested route behavior
- upload: pre-check, success/failure, file list feedback
