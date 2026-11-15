"""Serve the production SPA and its API from a single process."""

from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.main import app as api


class SPAFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code != 404
                or path.split("/", 1)[0] == "assets"
                or PurePosixPath(path).suffix
            ):
                raise
        # Let React Router resolve direct visits to client-side routes.
        return await super().get_response("index.html", scope)


app = FastAPI(openapi_url=None)
app.mount("/api", api)
app.mount(
    "/",
    SPAFiles(directory=Path(__file__).resolve().parents[1] / "frontend_dist", html=True),
)
