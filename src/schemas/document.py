from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    """Schema cho việc tạo document mới."""
    file_name: Optional[str] = None


class DocumentUpdate(BaseModel):
    """Schema cho việc cập nhật document."""
    file_name: Optional[str] = None
    extracted_text: Optional[str] = None
    status: Optional[ProcessingStatus] = None
    error_message: Optional[str] = None


class Document(BaseModel):
    """Schema cho document response đầy đủ."""
    id: UUID
    file_name: Optional[str] = None
    extracted_text: Optional[str] = None
    status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class DocumentSummary(BaseModel):
    """Schema cho document summary (không bao gồm extracted_text)."""
    id: UUID
    file_name: Optional[str] = None
    status: ProcessingStatus
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class DocumentExtractResponse(BaseModel):
    """Schema cho response khi trích xuất text từ PDF"""
    document_id: Optional[UUID] = None
    filename: str
    text_preview: str
    text_length: int
    chunks_created: int = 0


class DocumentExtractWithIdResponse(BaseModel):
    """Schema cho response khi trích xuất text từ PDF với ID của document"""
    id: UUID
    filename: str
    text_preview: str
    text_length: int
    chunks_created: int = 0


# Schemas mới cho chunking và tìm kiếm

class ChunkMetadata(BaseModel):
    """Metadata của một chunk"""
    document_id: str
    chunk_index: int
    length: Optional[int] = None
    chunking_method: Optional[str] = None
    chunking_size: Optional[int] = None
    chunking_overlap: Optional[int] = None
    processed_at: Optional[str] = None


class ChunkInfo(BaseModel):
    """Thông tin của một chunk"""
    chunk_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class ChunkResponse(BaseModel):
    """Response khi tạo chunks cho document"""
    document_id: UUID
    chunks_created: int
    status: str


class DocumentInfo(BaseModel):
    """Thông tin cơ bản của document"""
    id: UUID
    file_name: str


class SearchResultItem(BaseModel):
    """Item kết quả tìm kiếm"""
    chunk_id: str
    document: Optional[DocumentInfo] = None
    text: str
    metadata: Optional[Dict[str, Any]] = None
    score: float = Field(..., description="Điểm tương đồng (0-1)")


class SearchResponse(BaseModel):
    """Response khi tìm kiếm"""
    query: str
    results: List[SearchResultItem] = []
    count: int = 0


class VectorDBStats(BaseModel):
    """Thống kê về vector database"""
    collection_name: str
    document_chunks_count: int
    embedding_function: str
    embedding_model: Optional[str] = None


class ErrorResponse(BaseModel):
    """Schema cho response lỗi"""
    detail: str


class HealthResponse(BaseModel):
    """Schema cho health check response"""
    status: str
    service: Optional[str] = None