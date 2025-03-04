from typing import Optional
from pydantic import BaseModel


class DocumentExtractResponse(BaseModel):
    """Schema cho response khi trích xuất text từ PDF"""
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