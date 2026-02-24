from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    sku: str
    score: float
    examples: List[str]


class SearchResponse(BaseModel):
    query_id: str
    results: List[SearchResult]
    index_engine: str


class LiveSearchResult(BaseModel):
    sku: str
    score: float


class LiveSearchResponse(BaseModel):
    query_id: str
    results: List[LiveSearchResult]
    index_engine: str


class ExamplesResponse(BaseModel):
    sku: str
    examples: List[str]


class FeedbackRequest(BaseModel):
    query_id: str
    chosen_sku: str
    timestamp: Optional[datetime] = None


class FeedbackResponse(BaseModel):
    status: str
    saved_at: datetime


class HealthResponse(BaseModel):
    status: str
    dataset_root: str
    indexed_images: int
    indexed_skus: int
    index_ready: bool


class IndexStatusResponse(BaseModel):
    index_ready: bool
    indexed_images: int
    indexed_skus: int
    index_engine: str


class AdminItemsResponse(BaseModel):
    status: str
    sku: str
    added_images: int
    total_images: int
    total_skus: int
    index_engine: str


class AdminSkuImage(BaseModel):
    id: int
    sku: str
    filepath: str
    filename: str
    url: str


class AdminSkuImagesResponse(BaseModel):
    sku: str
    images: List[AdminSkuImage]


class AdminDeleteImagesRequest(BaseModel):
    sku: str
    admin_key: str
    filepaths: List[str]


class AdminDeleteImagesResponse(BaseModel):
    status: str
    sku: str
    removed_images: int
    removed_files: int
    remaining_sku_images: int
    total_images: int
    total_skus: int
    index_engine: str


class ReindexRequest(BaseModel):
    admin_key: str


class ReindexResponse(BaseModel):
    status: str
    sku_count: int
    image_count: int
    seconds: float
    skipped_images: int
    index_engine: str


class SkuExistsResponse(BaseModel):
    sku: str
    exists: bool


class SearchParams(BaseModel):
    k: int = Field(default=5, ge=1, le=20)
