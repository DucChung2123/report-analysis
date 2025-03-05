# src/schemas/document.py
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
    filename: str
    text_preview: str
    text_length: int


class DocumentExtractWithIdResponse(BaseModel):
    """Schema cho response khi trích xuất text từ PDF với ID của document"""
    id: UUID
    filename: str
    text_preview: str
    text_length: int


class ErrorResponse(BaseModel):
    """Schema cho response lỗi"""
    detail: str


class HealthResponse(BaseModel):
    """Schema cho health check response"""
    status: str
    service: Optional[str] = None