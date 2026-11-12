# avideo

Video analysis toolkit: per-pixel change heatmaps (with optional grayscale or per-channel thresholding), activity timelines, scene detection, optical flow, flicker analysis, video comparison and more.

It comes as a **command-line tool** and a **local web app** that share one Python core, so the same settings give the same results in both.

- Specification: [docs/spec.md](docs/spec.md) (core), [docs/spec-cli.md](docs/spec-cli.md) (CLI), [docs/spec-web.md](docs/spec-web.md) (web app)

## Project layout

```
src/avideo/
  core/       all analysis, shared by the CLI and the server
  cli/        command-line interface (Typer + Rich)
  server/     local web server (FastAPI); serves the built frontend from server/static/
frontend/     web app UI (React + TypeScript + Vite)
tests/        Python tests
docs/         specification
```

## Development setup

Requirements: Python ≥ 3.11, Node.js ≥ 20.

```bash
# Python: virtual environment with all libraries
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,av]"

# Frontend
cd frontend
npm install
```

## Everyday commands

```bash
source .venv/bin/activate

avideo --version          # CLI
pytest                    # Python tests
ruff check . && ruff format --check .

# Web app during development (two terminals):
avideo serve              # 1: Python server on http://127.0.0.1:8765
cd frontend && npm run dev   # 2: hot-reloading UI on http://localhost:5173 (proxies /api to the server)

# Build the UI into the Python package (then `avideo serve` serves it on :8765)
cd frontend && npm run build
```
