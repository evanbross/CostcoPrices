# ai: claude-sonnet-4-6 | 2026-06-19
"""
CostcoPrices launcher.

Usage:
  python main.py          — build frontend if stale, serve at http://costco.localhost
  python main.py --dev    — Vite + uvicorn with hot-reload, same Caddy URL

Ports are OS-assigned on every launch so this app never collides with other
local apps; http://costco.localhost (via the shared ../infra Caddy) is the
stable address. The direct ports are printed at startup.
"""
import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

# ai: claude-opus-5-5 | 2026-11-19
# Shared dev-runner and Caddy helpers: the zt-common package in ../infra/zt-common,
# a runtime dependency that `uv sync` installs into backend/.venv.
try:
    from zt_common import caddy_registry, devrun
except ImportError:
    print("[main] ERROR: zt-common is not installed. Check out the infra repo at ../infra,",
          "       then run: cd backend && uv sync  (and start main.py with backend/.venv's Python)",
          sep="\n", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
BACKEND_DIR = ROOT / "backend"

# ai: claude-opus-5-5 | 2026-09-28
# Status lines use non-ASCII (→, …). When stdout is redirected to a file or pipe on
# Windows, Python falls back to cp1252, which can't encode →, and the resulting
# UnicodeEncodeError kills the launcher without running _shutdown (orphaning uvicorn).
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Always use the backend venv's Python so all app deps (uvicorn, etc.) are available.
_IS_WINDOWS = platform.system() == "Windows"
_BACKEND_PYTHON = (
    BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if _IS_WINDOWS
    else BACKEND_DIR / ".venv" / "bin" / "python"
)

def _find_npm() -> str:
    path = shutil.which("npm")
    if path is None:
        print(
            "[main] ERROR: 'npm' not found on PATH.\n"
            "       Install Node.js from https://nodejs.org/ and restart.",
            file=sys.stderr,
        )
        sys.exit(1)
    return path

_NPM = _find_npm()
_procs: list[subprocess.Popen] = []  # type: ignore[type-arg]


_ENV = devrun.read_env_file(BACKEND_DIR / ".env")  # ai: claude-opus-5-5 | 2026-11-12
_CADDY_APP_NAME = _ENV.get("CADDY_APP_NAME", "costco")  # ai: claude-opus-5-5 | 2026-09-28


# ── process helpers ───────────────────────────────────────────────────────────

def _backend_python() -> str:
    if _BACKEND_PYTHON.exists():
        return str(_BACKEND_PYTHON)
    print(
        f"[main] WARNING: {_BACKEND_PYTHON} not found.\n"
        "       Run 'cd backend && uv sync' to create the virtual environment.",
        file=sys.stderr,
    )
    return sys.executable


def _run(cmd: list[str], cwd: Path, **kwargs) -> subprocess.Popen:  # type: ignore[type-arg]
    proc = subprocess.Popen(cmd, cwd=str(cwd), **kwargs)
    _procs.append(proc)
    return proc


def _shutdown(_sig: int, _frame: object) -> None:
    print("\n[main] Shutting down…")
    _caddy_deregister()
    for p in _procs:
        devrun.kill_process_tree(p)  # ai: claude-opus-5-5 | 2026-11-12
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ── npm / frontend helpers ────────────────────────────────────────────────────

def _npm(*args: str) -> int:
    result = subprocess.run([_NPM, *args], cwd=str(FRONTEND_DIR))
    return result.returncode


def _ensure_node_modules() -> None:
    if devrun.npm_install_needed(FRONTEND_DIR):  # ai: claude-opus-5-5 | 2026-11-12
        print("[main] Installing frontend dependencies…")
        if _npm("install") != 0:
            print("[main] ERROR: npm install failed", file=sys.stderr)
            sys.exit(1)


def _is_frontend_stale() -> bool:
    if not DIST_DIR.exists():
        return True
    dist_mtime = DIST_DIR.stat().st_mtime
    for f in (FRONTEND_DIR / "src").rglob("*"):
        if f.is_file() and f.stat().st_mtime > dist_mtime:
            return True
    for extra in ["index.html", "vite.config.ts", "tailwind.config.ts", "postcss.config.js"]:
        p = FRONTEND_DIR / extra
        if p.exists() and p.stat().st_mtime > dist_mtime:
            return True
    return False


def _build_frontend() -> None:
    print("[main] Building frontend…")
    if _npm("run", "build") != 0:
        print("[main] ERROR: Frontend build failed.", file=sys.stderr)
        sys.exit(1)
    print("[main] Frontend built successfully.")


# ── Caddy helpers ─────────────────────────────────────────────────────────────
# ai: claude-sonnet-5 | 2026-08-06

_CADDY_UNREACHABLE_MSG = (
    "[main] Caddy not reachable — {fallback}\n"
    "       Start the shared infra stack: cd ../infra && docker-compose up -d"
)


def _caddy_register_prod(backend_port: int) -> None:
    """Production: single route — all traffic to FastAPI (serves API + static files)."""
    caddy_registry.delete_route(f"app-{_CADDY_APP_NAME}-api")
    caddy_registry.delete_route(f"app-{_CADDY_APP_NAME}-frontend")
    ok = caddy_registry.register(_CADDY_APP_NAME, backend_port)
    if ok:
        print(f"[main] Caddy: http://{_CADDY_APP_NAME}.localhost → :{backend_port}")
    else:
        print(_CADDY_UNREACHABLE_MSG.format(fallback="direct access only."))


def _caddy_register_dev(backend_port: int, frontend_port: int) -> None:
    """Dev: /api/* → uvicorn, /* → Vite. No prefix stripping — backend owns the /api prefix."""
    caddy_registry.deregister(_CADDY_APP_NAME)

    routes = [
        {
            "@id": f"app-{_CADDY_APP_NAME}-api",
            "match": [{"host": [f"{_CADDY_APP_NAME}.localhost"], "path": ["/api", "/api/*"]}],
            "handle": [
                {"handler": "reverse_proxy", "upstreams": [{"dial": f"host.docker.internal:{backend_port}"}]},
            ],
        },
        {
            "@id": f"app-{_CADDY_APP_NAME}-frontend",
            "match": [{"host": [f"{_CADDY_APP_NAME}.localhost"]}],
            "handle": [
                {"handler": "reverse_proxy", "upstreams": [{"dial": f"host.docker.internal:{frontend_port}"}]},
            ],
        },
    ]
    ok = all(caddy_registry.register_route(r) for r in routes)
    if ok:
        print(f"[main] Caddy: http://{_CADDY_APP_NAME}.localhost  "
              f"(api→:{backend_port}, frontend→:{frontend_port})")
    else:
        print(_CADDY_UNREACHABLE_MSG.format(fallback="use direct ports instead."))


# ai: claude-opus-5-5 | 2026-11-12
def _caddy_deregister() -> None:
    if _caddy_reconciler is not None:
        # stop() waits out any in-flight re-registration, so it can't re-add a
        # route after we've removed it.
        _caddy_reconciler.stop()
    caddy_registry.deregister(_CADDY_APP_NAME)
    caddy_registry.delete_route(f"app-{_CADDY_APP_NAME}-api")
    caddy_registry.delete_route(f"app-{_CADDY_APP_NAME}-frontend")


# ai: claude-opus-5-5 | 2026-11-12
# Re-registers our routes if the Caddy container restarts while we run (Caddy keeps
# routes in memory only) or if Caddy was down at startup. Shared loop from
# zt_common.caddy_registry (../infra/zt-common), used by every app behind the dev Caddy.
_caddy_reconciler = None


def _start_caddy_reconciler(route_ids: list[str], register: Callable[[], None]) -> None:
    global _caddy_reconciler
    _caddy_reconciler = caddy_registry.RouteReconciler(route_ids, register)
    _caddy_reconciler.start()


# ── startup modes ─────────────────────────────────────────────────────────────

def _start_prod() -> None:
    _ensure_node_modules()
    if _is_frontend_stale():
        _build_frontend()
    else:
        print("[main] Frontend is up to date, skipping build.")

    port = devrun.free_port()  # ai: claude-opus-5-5 | 2026-09-28
    print(f"[main] Starting uvicorn on :{port}…")
    proc = _run(
        [
            _backend_python(), "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
        ],
        cwd=BACKEND_DIR,
    )

    print(f"[main] Waiting for backend on :{port}…")
    if not devrun.wait_for_port(port, proc=proc, timeout=30):
        print("[main] ERROR: Backend did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    _caddy_register_prod(port)  # ai: claude-opus-5-5 | 2026-11-12
    _start_caddy_reconciler([f"app-{_CADDY_APP_NAME}"], lambda: _caddy_register_prod(port))
    print("[main] App ready.")
    print(f"       http://{_CADDY_APP_NAME}.localhost")
    print(f"       http://localhost:{port}  (direct)")
    proc.wait()


def _start_dev() -> None:
    _ensure_node_modules()
    # ai: claude-opus-5-5 | 2026-09-28
    backend_port = devrun.free_port()
    frontend_port = devrun.free_port()

    print(f"[main] Starting uvicorn on :{backend_port} and Vite on :{frontend_port}…")

    backend_proc = _run(
        [
            _backend_python(), "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(backend_port),
            "--reload",
            "--reload-dir", "app",
        ],
        cwd=BACKEND_DIR,
    )
    # ai: claude-opus-5-5 | 2026-09-28
    # --strictPort makes Vite fail instead of silently hopping to another port,
    # which would leave the Caddy route pointing at the wrong one.
    # --host 127.0.0.1: Vite's default "localhost" resolves to IPv6 ::1 on Windows,
    # which devrun.wait_for_port (IPv4) never sees, so startup timed out.
    # COSTCO_API_PORT is how vite.config.ts learns where to proxy /api.
    vite_proc = _run(
        [_NPM, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
        cwd=FRONTEND_DIR,
        env={**os.environ, "COSTCO_API_PORT": str(backend_port)},
    )

    print("[main] Waiting for backend…")
    if not devrun.wait_for_port(backend_port, proc=backend_proc, timeout=30):
        print("[main] ERROR: Backend did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    print("[main] Waiting for Vite…")
    if not devrun.wait_for_port(frontend_port, proc=vite_proc, timeout=30):
        print("[main] ERROR: Vite did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    _caddy_register_dev(backend_port, frontend_port)  # ai: claude-opus-5-5 | 2026-11-12
    _start_caddy_reconciler(
        [f"app-{_CADDY_APP_NAME}-api", f"app-{_CADDY_APP_NAME}-frontend"],
        lambda: _caddy_register_dev(backend_port, frontend_port),
    )
    print("[main] Dev servers ready.")
    print(f"       http://{_CADDY_APP_NAME}.localhost  (via Caddy)")
    print(f"       http://127.0.0.1:{frontend_port}  (Vite direct)")  # ai: claude-opus-5-5 | 2026-09-28
    print(f"       http://127.0.0.1:{backend_port}  (API direct)")
    print("       Press Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1)
            dead = [p for p in _procs if p.poll() is not None]
            if dead:
                print("[main] A process exited unexpectedly.", file=sys.stderr)
                _shutdown(0, None)
    except KeyboardInterrupt:
        _shutdown(0, None)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CostcoPrices launcher")
    parser.add_argument("--dev", action="store_true", help="Development mode with hot-reload")
    args = parser.parse_args()

    if args.dev:
        _start_dev()
    else:
        _start_prod()


if __name__ == "__main__":
    main()
