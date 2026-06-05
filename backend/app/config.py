from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def _load_env() -> None:
    for env_path in [BACKEND_ROOT / ".env", BACKEND_ROOT / ".env.local"]:
        if env_path.exists():
            load_dotenv(env_path, override=True)


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value: str, default: Path) -> Path:
    raw = (value or "").strip()
    candidate = Path(raw).expanduser() if raw else default
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate.resolve()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    dataset_root: Path
    data_dir: Path
    storage_root: Path
    feedback_file: Path
    embedding_backend: str
    clip_model_id: str
    batch_size: int
    default_k: int
    retrieval_top_n: int
    max_examples_per_sku: int
    prototype_method: str
    allow_origins: List[str]
    enable_multicrop: bool
    enable_color_tiebreak: bool
    color_tie_threshold: float
    admin_key: str
    host: str
    port: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()

    dataset_root = _resolve_path(os.getenv("DATASET_ROOT", ""), PROJECT_ROOT / "Fotos")
    data_dir = _resolve_path(os.getenv("DATA_DIR", ""), BACKEND_ROOT / "data")
    storage_root = _resolve_path(os.getenv("STORAGE_ROOT", ""), BACKEND_ROOT / "storage")
    feedback_file = _resolve_path(
        os.getenv("FEEDBACK_FILE", ""),
        BACKEND_ROOT / "data" / "feedback" / "feedback.jsonl",
    )

    allow_origins_raw = os.getenv("ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    allow_origins = [v.strip() for v in allow_origins_raw.split(",") if v.strip()]

    settings = Settings(
        project_root=PROJECT_ROOT,
        dataset_root=dataset_root,
        data_dir=data_dir,
        storage_root=storage_root,
        feedback_file=feedback_file,
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "clip"),
        clip_model_id=os.getenv(
            "EMBEDDING_MODEL_ID",
            os.getenv("CLIP_MODEL_ID", "openai/clip-vit-base-patch32"),
        ),
        batch_size=int(os.getenv("BATCH_SIZE", "32")),
        default_k=int(os.getenv("DEFAULT_K", "5")),
        retrieval_top_n=int(os.getenv("RETRIEVAL_TOP_N", "50")),
        max_examples_per_sku=int(os.getenv("MAX_EXAMPLES_PER_SKU", "3")),
        prototype_method=os.getenv("PROTOTYPE_METHOD", "mean"),
        allow_origins=allow_origins if allow_origins else ["*"],
        enable_multicrop=_as_bool(os.getenv("ENABLE_MULTICROP", "true"), default=True),
        enable_color_tiebreak=_as_bool(os.getenv("ENABLE_COLOR_TIEBREAK", "true"), default=True),
        color_tie_threshold=float(os.getenv("COLOR_TIE_THRESHOLD", "0.015")),
        admin_key=os.getenv("ADMIN_KEY", "sku-admin-dev"),
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
    )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.feedback_file.parent.mkdir(parents=True, exist_ok=True)

    return settings
