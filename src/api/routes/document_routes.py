# src/api/routes/document_routes.py
import os
import shutil
from pathlib import Path
from typing import List
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.config import config
from src.core.logger import logger
from src.database.database import get_db
from src.database.model import Document
from src.document_processing.pdf_service import PDFService
from src.schemas.document import DocumentExtractResponse, HealthResponse

router = APIRouter(prefix="/documents", tags=["documents"])
pdf_service = PDFService()

UPLOAD_DIR = Path(config.get("storage.upload_dir", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)


@router.post("/upload", response_model=DocumentExtractResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF file, extract text and save to database
    
    Args:
        file (UploadFile): PDF file to upload
    
    Returns:
        DocumentExtractResponse: Response containing the extracted text
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    file_path = UPLOAD_DIR / file.filename
    
    try:
        # Lưu file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Xử lý validate và extract trước như logic cũ
        is_valid, error_msg = pdf_service.validate_pdf(file_path)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        extracted_text, error = pdf_service.extract_text(file_path)
        
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        # Lưu vào database
        document_id, _, _ = pdf_service.extract_and_save(db, file_path, file.filename)
        
        # Trả về response như cũ
        return DocumentExtractResponse(
            filename=file.filename,
            text_preview=extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            text_length=len(extracted_text)
        )
        
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        file.file.close()


@router.get("/", response_model=List[dict])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get list of all documents
    
    Returns:
        List[dict]: List of documents
    """
    documents = db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": doc.id,
            "file_name": doc.file_name,
            "status": doc.status.value,
            "created_at": doc.created_at,
            "processed_at": doc.processed_at
        }
        for doc in documents
    ]


@router.get("/{document_id}", response_model=dict)
async def get_document_details(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get document details by ID
    
    Args:
        document_id: Document ID
        
    Returns:
        dict: Document details
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "file_name": document.file_name,
        "status": document.status.value,
        "error_message": document.error_message,
        "text_length": len(document.extracted_text) if document.extracted_text else 0,
        "created_at": document.created_at,
        "processed_at": document.processed_at
    }


@router.get("/{document_id}/text", response_model=dict)
async def get_document_text(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get extracted text from document
    
    Args:
        document_id: Document ID
        
    Returns:
        dict: Document text
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.extracted_text:
        raise HTTPException(status_code=404, detail="No text available for this document")
    
    return {
        "id": document.id,
        "file_name": document.file_name,
        "text": document.extracted_text,
        "text_length": len(document.extracted_text)
    }


@router.delete("/{document_id}")
async def delete_document_by_id(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete document by ID
    
    Args:
        document_id: Document ID
        
    Returns:
        dict: Success message
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file if exists
    file_path = UPLOAD_DIR / document.file_name if document.file_name else None
    if file_path and file_path.exists():
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
    
    # Delete document from database
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    return HealthResponse(status="OK", service="document-processor")