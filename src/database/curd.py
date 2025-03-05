# src/database/crud.py
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from src.database.model import Document, ProcessingStatus


def create_document(db: Session, file_name: Optional[str] = None) -> Document:
    """
    Tạo một document mới trong database
    
    Args:
        db: Database session
        file_name: Tên file
        
    Returns:
        Document: Document đã tạo
    """
    db_document = Document(
        file_name=file_name,
        status=ProcessingStatus.PENDING
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def get_document(db: Session, document_id: UUID) -> Optional[Document]:
    """
    Lấy document theo ID
    
    Args:
        db: Database session
        document_id: ID của document
        
    Returns:
        Document hoặc None nếu không tìm thấy
    """
    return db.query(Document).filter(Document.id == document_id).first()


def get_documents(db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
    """
    Lấy danh sách documents
    
    Args:
        db: Database session
        skip: Số lượng bản ghi bỏ qua
        limit: Giới hạn số lượng bản ghi trả về
        
    Returns:
        List[Document]: Danh sách document
    """
    return db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()


def save_extracted_text(db: Session, document_id: UUID, text: str) -> Document:
    """
    Lưu văn bản đã trích xuất vào document
    
    Args:
        db: Database session
        document_id: ID của document
        text: Văn bản đã trích xuất
        
    Returns:
        Document: Document đã cập nhật
    """
    document = get_document(db, document_id)
    if document:
        document.extracted_text = text
        document.status = ProcessingStatus.COMPLETED
        document.processed_at = datetime.now()
        db.commit()
        db.refresh(document)
    return document


def set_document_error(db: Session, document_id: UUID, error_message: str) -> Document:
    """
    Đặt trạng thái lỗi cho document
    
    Args:
        db: Database session
        document_id: ID của document
        error_message: Thông báo lỗi
        
    Returns:
        Document: Document đã cập nhật
    """
    document = get_document(db, document_id)
    if document:
        document.status = ProcessingStatus.FAILED
        document.error_message = error_message
        document.processed_at = datetime.now()
        db.commit()
        db.refresh(document)
    return document


def delete_document(db: Session, document_id: UUID) -> bool:
    """
    Xóa document
    
    Args:
        db: Database session
        document_id: ID của document
        
    Returns:
        bool: True nếu xóa thành công, False nếu không tìm thấy
    """
    document = get_document(db, document_id)
    if document:
        db.delete(document)
        db.commit()
        return True
    return False