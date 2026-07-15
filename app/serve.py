"""Dev server entrypoint.

    python -m app.serve --reload

Exists because of one Windows trap. Playwright launches its driver as a
subprocess, and asyncio can only spawn subprocesses on a ProactorEventLoop.
Uvicorn picks a SelectorEventLoop whenever it manages child processes itself
(`--reload` or `--workers`) -- so `uvicorn app.main:app --reload` on Windows
dies at startup with a bare NotImplementedError out of create_subprocess_exec.

Plain `uvicorn app.main:app` (no reload) already works, since that path gets the
Proactor loop. This module makes --reload work too, by forcing the loop back.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn
from uvicorn.supervisors import ChangeReload


class ProactorConfig(uvicorn.Config):
    """Uvicorn config that keeps the Proactor loop even under --reload.

    Defined at module level (not a lambda) so it survives being pickled into the
    reloader's spawned child process on Windows.
    """

    def get_loop_factory(self):  # type: ignore[override]
        if sys.platform == "win32":
            return asyncio.ProactorEventLoop
        return super().get_loop_factory()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    config = ProactorConfig(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    server = uvicorn.Server(config)

    if config.should_reload:
        sock = config.bind_socket()
        ChangeReload(config, target=server.run, sockets=[sock]).run()
    else:
        server.run()


if __name__ == "__main__":
    main()
