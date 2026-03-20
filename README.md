# HILIGHTer Digital Twin

HILIGHTer is a Python-first FLIM engineering workspace centered on a Qt desktop application, a shared numerical backend, and automation surfaces for scripts, HTTP clients, and MCP hosts.

## Start The Desktop App

```powershell
python\run_desktop.bat
```

## Repository Layout

- `python/`
  Active application code, launchers, profiles, tests, and developer tools.
- `python/backend/`
  Shared physics engine, service API, storage, and importers.
- `python/gui/`
  Qt desktop workspace and widgets.
- `python/tools/`
  Utility scripts such as MCP smoke tests and benchmark-report helpers.
- `python/tests/`
  Automated Python tests.
- `docs/`
  Architecture notes and the HTML operator manual.
- `resources/`
  Static supporting assets.

## Useful Validation Commands

```powershell
python -m py_compile python\desktop_app.py python\backend\*.py python\gui\main_window.py
pytest python/tests
python python\tools\mcp_smoke_test.py
```
