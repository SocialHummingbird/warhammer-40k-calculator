# Repository Guidelines

## Project Structure & Module Organization
- `warhammer/` — core logic (`calculator.py`, helpers)
- `main.py` — CLI entry
- `tests/` — unit tests
- `requirements.txt` — deps

## Build, Test, and Development
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
