## 1.6.0 (2026-08-02)

### Feat

- **cli**: add an --output option naming the generated files

## 1.5.0 (2026-08-02)

### Feat

- **provenance**: write a human-readable provenance log on fetch
- **search**: per-repository search strategy customisation

### Fix

- **provenance**: escape Unicode line and paragraph separators too
- **provenance**: escape control characters from remote metadata in the log

## 1.4.0 (2026-08-02)

### Feat

- **access**: port the axe-core WCAG gate to Python
- **print**: produce the tagged PDF with Playwright for Python
- **renderer**: run citeproc-js in-process on an embedded V8 engine

## 1.3.0 (2026-08-02)

### Feat

- **sources**: support any number of repositories of each type

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
