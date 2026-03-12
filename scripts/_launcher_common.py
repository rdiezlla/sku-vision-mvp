from __future__ import annotations

import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
SCRIPTS_DIR = REPO_ROOT / "scripts"
CERTS_DIR = REPO_ROOT / "certs"
RUN_LOG_DIR = REPO_ROOT / ".run_logs"

INDEX_REQUIRED_FILES = [
    BACKEND_DIR / "data" / "sku_prototypes.npy",
    BACKEND_DIR / "data" / "image_embeddings.npy",
    BACKEND_DIR / "data" / "mapping.json",
]

BACKEND_API_PATH_PREFIXES = [
    "/search",
    "/search_live",
    "/feedback",
    "/sku/*",
    "/admin/*",
    "/index/*",
    "/health",
    "/api/",
    "/api/*",
    "/reference-images/*",
    "/storage-images/*",
]


@dataclass
class RunningProcess:
    name: str
    process: subprocess.Popen
    log_file: Path


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def parse_env_file(path: Path) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    if not path.exists():
        return parsed

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
            value = value[1:-1]
        parsed[key] = value
    return parsed


def load_project_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env: Dict[str, str] = {}

    ordered_files = [
        BACKEND_DIR / ".env",
        BACKEND_DIR / ".env.local",
        FRONTEND_DIR / ".env",
        FRONTEND_DIR / ".env.local",
    ]

    for env_file in ordered_files:
        env.update(parse_env_file(env_file))

    env.update(os.environ)

    if extra:
        env.update({k: str(v) for k, v in extra.items()})

    return env


def ensure_run_log_dir() -> Path:
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return RUN_LOG_DIR


def venv_python() -> Path:
    if is_windows():
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def npm_command() -> str:
    return "npm.cmd" if is_windows() else "npm"


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def backend_index_exists() -> bool:
    return all(path.exists() for path in INDEX_REQUIRED_FILES)


def local_ip_candidates() -> List[str]:
    candidates: List[str] = []

    # Primary route-based detection.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            candidates.append(ip)
    except Exception:
        pass

    # Hostname based fallback.
    for value in socket.gethostbyname_ex(socket.gethostname())[2]:
        if value and not value.startswith("127."):
            candidates.append(value)

    deduped: List[str] = []
    for ip in candidates:
        if ip not in deduped:
            deduped.append(ip)

    return deduped


def preferred_local_ip(default: str = "127.0.0.1") -> str:
    candidates = local_ip_candidates()
    return candidates[0] if candidates else default


def run_checked(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> None:
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def start_logged_process(
    name: str,
    cmd: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_filename: str,
) -> RunningProcess:
    ensure_run_log_dir()
    log_file = RUN_LOG_DIR / log_filename
    handle = log_file.open("w", encoding="utf-8")

    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    return RunningProcess(name=name, process=process, log_file=log_file)


def wait_until_healthy(process: RunningProcess, timeout_seconds: float = 4.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.process.poll() is not None:
            return False
        time.sleep(0.15)
    return process.process.poll() is None


def terminate_processes(processes: Iterable[RunningProcess]) -> None:
    # Reverse order to stop frontend/proxy first and backend last.
    for item in reversed(list(processes)):
        proc = item.process
        if proc.poll() is not None:
            continue
        try:
            if is_windows():
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
        except Exception:
            pass

    deadline = time.time() + 5
    for item in reversed(list(processes)):
        proc = item.process
        if proc.poll() is not None:
            continue
        remaining = max(0.1, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def print_process_logs_hint(processes: Iterable[RunningProcess]) -> None:
    for item in processes:
        print(f"[{item.name}] log: {item.log_file}")


def python_cmd() -> str:
    return sys.executable


def read_setting(env: Dict[str, str], key: str, default: str) -> str:
    value = str(env.get(key, "")).strip()
    return value if value else default


def build_allow_origins(origins: Iterable[str]) -> str:
    clean = [origin.strip() for origin in origins if origin and origin.strip()]
    deduped: List[str] = []
    for origin in clean:
        if origin not in deduped:
            deduped.append(origin)
    return ",".join(deduped)
