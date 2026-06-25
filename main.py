# ai: claude-sonnet-4-6 | 2026-06-19
"""
CostcoPrices launcher.

Usage:
  python main.py          — build frontend if stale, serve at http://costcoprices.localhost
  python main.py --dev    — Vite :5173 + uvicorn :8000 with hot-reload, same Caddy URL
"""
import argparse
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
BACKEND_DIR = ROOT / "backend"

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


# ── .env helpers ──────────────────────────────────────────────────────────────

def _parse_env() -> dict[str, str]:
    env_file = BACKEND_DIR / ".env"
    result: dict[str, str] = {}
    if not env_file.exists():
        return result
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


_ENV = _parse_env()
_CADDY_ADMIN_URLS = _ENV.get("CADDY_ADMIN_URLS", "http://localhost:2019")
_CADDY_ADMIN_URL_LIST = [u.strip() for u in _CADDY_ADMIN_URLS.split(",") if u.strip()]
_CADDY_APP_NAME = _ENV.get("CADDY_APP_NAME", "costcoprices")


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
        try:
            if _IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                    capture_output=True, check=False,
                )
            else:
                p.terminate()
        except OSError:
            pass
    time.sleep(1)
    for p in _procs:
        try:
            p.kill()
        except OSError:
            pass
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ── npm / frontend helpers ────────────────────────────────────────────────────

def _npm(*args: str) -> int:
    result = subprocess.run([_NPM, *args], cwd=str(FRONTEND_DIR))
    return result.returncode


def _ensure_node_modules() -> None:
    nm = FRONTEND_DIR / "node_modules"
    pkg = FRONTEND_DIR / "package.json"
    if not nm.exists() or pkg.stat().st_mtime > nm.stat().st_mtime:
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


# ── port helpers ──────────────────────────────────────────────────────────────

def _wait_for_port(port: int, timeout: int = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ── Caddy helpers ─────────────────────────────────────────────────────────────

def _caddy_request(method: str, path: str, body: object | None = None) -> bool:
    """Try each Caddy admin URL in order; return True on the first success."""
    data = json.dumps(body).encode() if body is not None else None
    for base_url in _CADDY_ADMIN_URL_LIST:
        try:
            req = urllib.request.Request(
                f"{base_url}{path}",
                data=data,
                headers={"Content-Type": "application/json"} if data else {},
                method=method,
            )
            urllib.request.urlopen(req, timeout=3)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            continue
    return False


def _caddy_delete_route(route_id: str) -> None:
    _caddy_request("DELETE", f"/id/{route_id}")


def _caddy_register_prod(backend_port: int) -> None:
    """Production: single route — all traffic to FastAPI (serves API + static files)."""
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-api")
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-frontend")
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-all")

    route = {
        "@id": f"app-{_CADDY_APP_NAME}-all",
        "match": [{"host": [f"{_CADDY_APP_NAME}.localhost"]}],
        "handle": [
            {"handler": "reverse_proxy", "upstreams": [{"dial": f"host.docker.internal:{backend_port}"}]},
        ],
    }
    ok = _caddy_request("POST", "/config/apps/http/servers/dev/routes", route)
    if ok:
        print(f"[main] Caddy: http://{_CADDY_APP_NAME}.localhost → :{backend_port}")
    else:
        print("[main] Caddy not reachable — direct access only.")


def _caddy_register_dev(backend_port: int, frontend_port: int) -> None:
    """Dev: /api/* → uvicorn, /* → Vite. No prefix stripping — backend owns the /api prefix."""
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-api")
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-frontend")
    _caddy_delete_route(f"app-{_CADDY_APP_NAME}-all")

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
    ok = all(_caddy_request("POST", "/config/apps/http/servers/dev/routes", r) for r in routes)
    if ok:
        print(f"[main] Caddy: http://{_CADDY_APP_NAME}.localhost  "
              f"(api→:{backend_port}, frontend→:{frontend_port})")
    else:
        print("[main] Caddy not reachable — use direct ports instead.")


def _caddy_deregister() -> None:
    for suffix in ("all", "api", "frontend"):
        _caddy_delete_route(f"app-{_CADDY_APP_NAME}-{suffix}")


# ── startup modes ─────────────────────────────────────────────────────────────

def _start_prod() -> None:
    _ensure_node_modules()
    if _is_frontend_stale():
        _build_frontend()
    else:
        print("[main] Frontend is up to date, skipping build.")

    port = int(os.environ.get("PORT", _ENV.get("PORT", "8000")))
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
    if not _wait_for_port(port):
        print("[main] ERROR: Backend did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    _caddy_register_prod(port)
    print(f"[main] App ready.")
    print(f"       http://{_CADDY_APP_NAME}.localhost")
    print(f"       http://localhost:{port}  (direct)")
    proc.wait()


def _start_dev() -> None:
    _ensure_node_modules()
    backend_port = int(os.environ.get("PORT", _ENV.get("PORT", "8000")))
    frontend_port = 5173

    print(f"[main] Starting uvicorn on :{backend_port} and Vite on :{frontend_port}…")

    _run(
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
    _run([_NPM, "run", "dev"], cwd=FRONTEND_DIR)

    print("[main] Waiting for backend…")
    if not _wait_for_port(backend_port):
        print("[main] ERROR: Backend did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    print("[main] Waiting for Vite…")
    if not _wait_for_port(frontend_port):
        print("[main] ERROR: Vite did not start in time.", file=sys.stderr)
        _shutdown(0, None)

    _caddy_register_dev(backend_port, frontend_port)
    print("[main] Dev servers ready.")
    print(f"       http://{_CADDY_APP_NAME}.localhost  (via Caddy)")
    print(f"       http://localhost:{frontend_port}       (Vite direct)")
    print(f"       http://localhost:{backend_port}        (API direct)")
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
