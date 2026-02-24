from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from backend.app.config import get_settings
from backend.app.schemas import (
    AdminDeleteImagesRequest,
    AdminDeleteImagesResponse,
    AdminItemsResponse,
    AdminSkuImagesResponse,
    ExamplesResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IndexStatusResponse,
    LiveSearchResponse,
    ReindexRequest,
    ReindexResponse,
    SkuExistsResponse,
    SearchResponse,
)
from backend.index.store import SkuSearchIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("sku_vision.api")

settings = get_settings()
search_index = SkuSearchIndex(
    dataset_root=settings.dataset_root,
    data_dir=settings.data_dir,
    storage_root=settings.storage_root,
    model_id=settings.clip_model_id,
    batch_size=settings.batch_size,
    prototype_method=settings.prototype_method,
)

app = FastAPI(title="SKU Vision MVP", version="0.2.0")

if "*" in settings.allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if settings.dataset_root.exists():
    app.mount("/reference-images", StaticFiles(directory=str(settings.dataset_root)), name="reference-images")
if settings.storage_root.exists():
    app.mount("/storage-images", StaticFiles(directory=str(settings.storage_root)), name="storage-images")


@app.on_event("startup")
def startup() -> None:
    try:
        search_index.load()
        logger.info("Índices cargados en startup")
    except Exception as exc:
        logger.warning("Índices no cargados en startup: %s", exc)


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    status = search_index.status()
    return HealthResponse(
        status="ok",
        dataset_root=str(settings.dataset_root),
        indexed_images=status["indexed_images"],
        indexed_skus=status["indexed_skus"],
        index_ready=status["index_ready"],
    )


@app.get("/index/status", response_model=IndexStatusResponse)
@app.get("/api/index/status", response_model=IndexStatusResponse)
def index_status() -> IndexStatusResponse:
    return IndexStatusResponse(**search_index.status())


@app.post("/search", response_model=SearchResponse)
@app.post("/api/search", response_model=SearchResponse)
async def search_image(
    file: UploadFile = File(...),
    k: int = Form(default=settings.default_k),
    top_k: Optional[int] = Form(default=None),
) -> SearchResponse:
    final_k = top_k if top_k is not None else k
    if final_k <= 0:
        raise HTTPException(status_code=400, detail="k debe ser mayor que 0")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Imagen vacía")

    filename = (file.filename or "").lower()

    try:
        image = Image.open(BytesIO(payload)).convert("RGB")
    except UnidentifiedImageError as exc:
        if filename.endswith(".heic") or filename.endswith(".heif"):
            raise HTTPException(
                status_code=400,
                detail="Formato HEIC/HEIF no soportado en este backend. Exporta/sube JPG o PNG.",
            ) from exc
        raise HTTPException(status_code=400, detail="Formato de imagen no válido") from exc

    try:
        result = search_index.search(
            query_image=image,
            k=final_k,
            retrieval_top_n=settings.retrieval_top_n,
            max_examples=settings.max_examples_per_sku,
            enable_multicrop=settings.enable_multicrop,
            enable_color_tiebreak=settings.enable_color_tiebreak,
            color_tie_threshold=settings.color_tie_threshold,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Error interno en /search")
        raise HTTPException(status_code=500, detail=f"Error interno en búsqueda: {exc}") from exc

    return SearchResponse(**result)


@app.post("/search_live", response_model=LiveSearchResponse)
@app.post("/api/search_live", response_model=LiveSearchResponse)
async def search_live(
    file: UploadFile = File(...),
    k: int = Form(default=5),
    enable_multicrop: Optional[bool] = Form(default=None),
) -> LiveSearchResponse:
    if k <= 0:
        raise HTTPException(status_code=400, detail="k debe ser mayor que 0")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Imagen vacía")

    filename = (file.filename or "").lower()
    try:
        image = Image.open(BytesIO(payload)).convert("RGB")
    except UnidentifiedImageError as exc:
        if filename.endswith(".heic") or filename.endswith(".heif"):
            raise HTTPException(
                status_code=400,
                detail="Formato HEIC/HEIF no soportado en este backend. Exporta/sube JPG o PNG.",
            ) from exc
        raise HTTPException(status_code=400, detail="Formato de imagen no válido") from exc

    use_multicrop = settings.enable_multicrop if enable_multicrop is None else bool(enable_multicrop)

    try:
        result = search_index.search(
            query_image=image,
            k=k,
            retrieval_top_n=settings.retrieval_top_n,
            max_examples=0,
            enable_multicrop=use_multicrop,
            enable_color_tiebreak=settings.enable_color_tiebreak,
            color_tie_threshold=settings.color_tie_threshold,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Error interno en /search_live")
        raise HTTPException(status_code=500, detail=f"Error interno en búsqueda live: {exc}") from exc

    light_results = [{"sku": row["sku"], "score": row["score"]} for row in result.get("results", [])]
    return LiveSearchResponse(
        query_id=result.get("query_id", ""),
        results=light_results,
        index_engine=result.get("index_engine", search_index.index_engine),
    )


@app.get("/sku/{sku}/examples", response_model=ExamplesResponse)
def sku_examples(sku: str, limit: int = 3) -> ExamplesResponse:
    examples = search_index.get_examples(sku=sku, limit=max(limit, 1))
    if not examples:
        raise HTTPException(status_code=404, detail=f"SKU {sku} no encontrado")
    return ExamplesResponse(sku=sku, examples=examples)


@app.post("/feedback", response_model=FeedbackResponse)
@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    now = datetime.now(timezone.utc)
    feedback_row = {
        "saved_at": now.isoformat(),
        "query_id": payload.query_id,
        "chosen_sku": payload.chosen_sku,
        "timestamp": (payload.timestamp or now).isoformat(),
    }

    with settings.feedback_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(feedback_row, ensure_ascii=False) + "\n")

    return FeedbackResponse(status="ok", saved_at=now)


@app.post("/admin/items", response_model=AdminItemsResponse)
async def add_admin_items(
    sku: str = Form(...),
    admin_key: str = Form(...),
    files: Optional[List[UploadFile]] = File(default=None),
    files_array: Optional[List[UploadFile]] = File(default=None, alias="files[]"),
) -> AdminItemsResponse:
    if admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Clave admin inválida")

    incoming_files = (files or []) + (files_array or [])

    payloads = []
    for file in incoming_files:
        content = await file.read()
        if not content:
            continue
        payloads.append((file.filename or "upload.jpg", content))

    if not payloads:
        raise HTTPException(status_code=400, detail="No se recibieron imágenes válidas")

    try:
        stats = search_index.append_items(sku=sku, files=payloads)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AdminItemsResponse(status="ok", **stats)


@app.get("/admin/sku_exists", response_model=SkuExistsResponse)
def admin_sku_exists(
    sku: str = Query(..., min_length=1),
    admin_key: str = Query(..., min_length=1),
) -> SkuExistsResponse:
    if admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Clave admin inválida")

    clean_sku = sku.strip()
    return SkuExistsResponse(sku=clean_sku, exists=search_index.sku_exists(clean_sku))


@app.get("/admin/sku_images", response_model=AdminSkuImagesResponse)
def admin_sku_images(
    sku: str = Query(..., min_length=1),
    admin_key: str = Query(..., min_length=1),
) -> AdminSkuImagesResponse:
    if admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Clave admin inválida")

    clean_sku = sku.strip()
    images = search_index.list_sku_images(sku=clean_sku, storage_only=True)
    return AdminSkuImagesResponse(sku=clean_sku, images=images)


@app.post("/admin/sku_images/delete", response_model=AdminDeleteImagesResponse)
def admin_delete_sku_images(payload: AdminDeleteImagesRequest) -> AdminDeleteImagesResponse:
    if payload.admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Clave admin inválida")

    try:
        stats = search_index.remove_sku_images(sku=payload.sku, filepaths=payload.filepaths)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AdminDeleteImagesResponse(status="ok", **stats)


@app.post("/admin/reindex", response_model=ReindexResponse)
def reindex(payload: ReindexRequest) -> ReindexResponse:
    if payload.admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Clave admin inválida")

    stats = search_index.build(data_dir=settings.dataset_root, include_storage=True)
    return ReindexResponse(
        status="ok",
        sku_count=stats["sku_count"],
        image_count=stats["image_count"],
        seconds=stats["seconds"],
        skipped_images=stats["skipped_images"],
        index_engine=stats["index_engine"],
    )
