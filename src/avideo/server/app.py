"""FastAPI application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from avideo import __version__

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="avideo", version=__version__, docs_url=None, redoc_url=None)


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"version": __version__}


# The built React app (frontend/ → `npm run build`). Mounted last so /api routes win.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
