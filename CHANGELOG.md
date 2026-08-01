## 1.2.0 (2026-08-01)

### Feat

- **sources**: InvenioRDM (KC Works) source with cross-repository deduplication
- **config**: per-user configuration directory with plaintext identity and a CONFIG argument
- **pdf**: print a tagged, outlined PDF headlessly and gate outputs with axe-core
- **accessibility**: semantic lists, language, and AAA typography in the templates and sections
- **accessibility**: AAA contrast palette, accessible link names, and list semantics in the generator

### Fix

- **accessibility**: enforce output checks in CI
- **repository**: handle current Invenio records
- **config**: isolate profiles and anchor project paths
- **repository**: preserve refresh failure semantics

### Perf

- **build**: render citations in-process and drop the citeproc-js-server fleet

## 1.1.0 (2026-08-01)

### Feat

- **architecture**: move to uv, pyproject.toml, and a packaged cv module
