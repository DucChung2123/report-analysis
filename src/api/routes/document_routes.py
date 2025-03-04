import os
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from src.core.config import config
from src.document_processing.pdf_extractor import PDFExtractor
from src.schemas.document import DocumentExtractResponse, HealthResponse

router = APIRouter(prefix="/documents", tags=["documents"])
pdf_extractor = PDFExtractor()

UPLOAD_DIR = Path(config.get("document.upload_dir", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=DocumentExtractResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF file and extract text
    
    Args:
        file (UploadFile): PDF file to upload
    
    Returns:
        DocumentExtractResponse: Response containing the extracted text
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    file_path = UPLOAD_DIR / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        is_valid, error_msg = pdf_extractor.validate_pdf(file_path)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        extracted_text, error = pdf_extractor.extract_text(file_path)
        
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        return DocumentExtractResponse(
            filename=file.filename,
            text_preview=extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            text_length=len(extracted_text)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        file.file.close()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    return HealthResponse(status="OK", service="document-processor")