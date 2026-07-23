"""Tiny static SPA server used only by the Playwright web harness."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parents[1] / "apps" / "client" / "dist"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        candidate = ROOT / self.path.lstrip("/").split("?", 1)[0]
        if not candidate.exists():
            self.path = "/index.html"
        super().do_GET()


ThreadingHTTPServer(("127.0.0.1", 4173), Handler).serve_forever()
