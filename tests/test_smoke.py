"""Smoke tests: the environment, CLI entry point and server are wired up."""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import avideo
from avideo.cli.app import app as cli_app
from avideo.server.app import app as server_app


def test_cli_version() -> None:
    result = CliRunner().invoke(cli_app, ["--version"])
    assert result.exit_code == 0
    assert avideo.__version__ in result.output


def test_server_version() -> None:
    response = TestClient(server_app).get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"version": avideo.__version__}


def test_core_dependencies_import() -> None:
    import av  # noqa: F401
    import cv2  # noqa: F401
    import matplotlib  # noqa: F401
    import numpy  # noqa: F401
    import PIL  # noqa: F401
    import pydantic  # noqa: F401
    import skimage  # noqa: F401
    import tomli_w  # noqa: F401
