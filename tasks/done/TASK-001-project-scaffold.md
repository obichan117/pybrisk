# TASK-001: Project Scaffold

**Status**: todo
**Priority**: high

## Description
Set up the project skeleton: `pyproject.toml`, `src/pybrisk/` layout, dev dependencies, ruff/mypy config, MkDocs setup, and `.claude/CLAUDE.md`.

## Acceptance Criteria
- [ ] `pyproject.toml` with hatchling, Python 3.10+, all deps (httpx, pydantic, pandas, optional playwright)
- [ ] `src/pybrisk/` directory with `__init__.py` and all `_internal/` stubs
- [ ] `ruff` and `mypy` configured in `pyproject.toml`
- [ ] `mkdocs.yml` with Material theme
- [ ] `.claude/CLAUDE.md` with quick start, architecture overview, key files
- [ ] `uv run pytest` passes (empty test suite)
- [ ] `uv run mkdocs build --strict` passes
