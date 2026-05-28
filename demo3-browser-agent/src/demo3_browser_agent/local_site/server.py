from __future__ import annotations

import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    network_down_until = {"value": 0.0}

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/network-drop")
    async def network_drop() -> FileResponse:
        network_down_until["value"] = time.time() + 5
        return FileResponse(STATIC_DIR / "network_drop.html")

    @app.get("/cookie-wall")
    async def cookie_wall() -> FileResponse:
        return FileResponse(STATIC_DIR / "cookie_wall.html")

    @app.post("/api/network-submit")
    async def network_submit(request: Request) -> JSONResponse:
        if time.time() < network_down_until["value"]:
            return JSONResponse({"ok": False, "message": "模拟断网中，请稍后重试"}, status_code=503)
        payload = await request.json()
        return JSONResponse({"ok": True, "confirmation": "INC-NETWORK-0427", "payload": payload})

    return app


class LocalSiteServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        if self._server:
            return self.url
        config = uvicorn.Config(create_app(), host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
