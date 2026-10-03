# TextField

TextField takes a single value — data-slot paths, search, filters.

**Props:** `label`, `value` / `defaultValue`, `onChange`, `placeholder`, `hint`, `error` (string), `mono` (bool — use for file paths), `disabled`.

- Sits on `surface-sunken` with a `line-strong` border; focus shows `shadow-focus`.
- Data-slot path inputs are `mono` and carry the slot's description as `hint`.
- Errors say what to do: "File not found — choose a .las or .laz file".
