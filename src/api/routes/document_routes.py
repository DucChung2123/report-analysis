import os
import shutil
from pathlib import Path
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.config import config
from src.core.logger import logger
from src.database.database import get_db
from src.database.model import Document
from src.document_processing.pdf_service import PDFService
from src.vector_db.chroma_service import ChromaService
from src.schemas.document import DocumentExtractResponse, HealthResponse, SearchResponse


router = APIRouter(prefix="/documents", tags=["documents"])
pdf_service = PDFService()
vector_db = ChromaService()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    return HealthResponse(status="OK", service="document-processor")

# Get upload directory from config
UPLOAD_DIR = Path(config.get("storage.upload_dir", "./data/uploads"))
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# Get max upload size from config (in MB)
MAX_UPLOAD_SIZE = config.get("storage.max_upload_size", 50) * 1024 * 1024  # Convert to bytes


@router.post("/upload", response_model=DocumentExtractResponse)
async def upload_document(
    file: UploadFile = File(...),
    auto_chunk: bool = Query(None, description="Automatically chunk document and store in vector DB"),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF file, extract text and save to database
    
    Args:
        file (UploadFile): PDF file to upload
        auto_chunk (bool): Whether to automatically chunk and store in vector DB (overrides config)
    
    Returns:
        DocumentExtractResponse: Response containing the extracted text
    """
    # Check file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Check file size
    file_size = 0
    content = await file.read()
    file_size = len(content)
    await file.seek(0)  # Reset file position
    
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE / (1024 * 1024)} MB"
        )
    
    file_path = UPLOAD_DIR / file.filename
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process PDF and extract text
        is_valid, error_msg = pdf_service.validate_pdf(file_path)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Extract text
        extracted_text, error = pdf_service.extract_text(file_path)
        
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        # Save to database
        document_id, _, _ = pdf_service.extract_and_save(db, file_path, file.filename)
        
        # Process chunks if auto_chunk parameter is provided (overrides default config)
        chunk_count = 0
        if auto_chunk is not None:
            # Override the default auto_chunk setting from service
            use_auto_chunk = auto_chunk
        else:
            # Use the default from config
            use_auto_chunk = pdf_service.auto_chunk
            
        if use_auto_chunk and extracted_text:
            chunk_count, chunk_error = pdf_service.process_chunks(document_id, extracted_text)
            if chunk_error:
                logger.warning(f"Error in chunking process: {chunk_error}")
        
        return DocumentExtractResponse(
            document_id=document_id,
            filename=file.filename,
            text_preview=extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            text_length=len(extracted_text),
            chunks_created=chunk_count
        )
        
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        file.file.close()


@router.post("/{document_id}/chunk", response_model=dict)
async def process_document_chunks(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Process a document into chunks and store in vector database
    
    Args:
        document_id: Document ID
        
    Returns:
        dict: Processing result
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.extracted_text:
        raise HTTPException(status_code=400, detail="Document has no extracted text")
    
    # Process chunks
    chunk_count, error_msg = pdf_service.process_chunks(document_id, document.extracted_text)
    
    if error_msg:
        raise HTTPException(status_code=500, detail=error_msg)
    
    return {
        "document_id": document_id,
        "chunks_created": chunk_count,
        "status": "success"
    }


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    query: str = Query(..., description="Search query text"),
    document_id: Optional[UUID] = Query(None, description="Optional document ID to limit search"),
    limit: int = Query(5, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Search for documents using vector similarity
    
    Args:
        query: Search query
        document_id: Optional document ID to limit search
        limit: Number of results to return
        
    Returns:
        SearchResponse: Search results
    """
    # Perform search
    results = vector_db.search(
        query=query, 
        n_results=limit,
        document_id=document_id
    )
    
    # Format results
    search_results = []
    if results and "ids" in results and results["ids"]:
        for i, result_ids in enumerate(results["ids"]):
            for j, chunk_id in enumerate(result_ids):
                # Extract document ID from chunk ID (format: "{document_id}_{chunk_index}")
                doc_id = chunk_id.split("_")[0] if "_" in chunk_id else None
                
                # Get document info if document ID is valid
                doc_info = None
                if doc_id:
                    try:
                        uuid_doc_id = UUID(doc_id)
                        document = db.query(Document).filter(Document.id == uuid_doc_id).first()
                        if document:
                            doc_info = {
                                "id": document.id,
                                "file_name": document.file_name
                            }
                    except ValueError:
                        pass
                
                search_results.append({
                    "chunk_id": chunk_id,
                    "document": doc_info,
                    "text": results["documents"][i][j] if "documents" in results else "",
                    "metadata": results["metadatas"][i][j] if "metadatas" in results else {},
                    "score": 1 - results["distances"][i][j] if "distances" in results else 0
                })
    
    return SearchResponse(
        query=query,
        results=search_results,
        count=len(search_results)
    )


@router.get("/{document_id}/chunks", response_model=List[dict])
async def get_document_chunks(
    document_id: UUID,
    limit: int = Query(100, description="Maximum number of chunks to return")
):
    """
    Get all chunks for a document
    
    Args:
        document_id: Document ID
        limit: Maximum number of chunks to return
        
    Returns:
        List[dict]: List of chunks
    """
    try:
        # Search chunks with document_id filter (empty query returns all chunks)
        results = vector_db.search(
            query="",  # Empty query to get all chunks
            n_results=limit,
            document_id=document_id,
            filter_dict={"document_id": str(document_id)}
        )
        
        chunks = []
        if results and "ids" in results and results["ids"]:
            for i, result_ids in enumerate(results["ids"]):
                for j, chunk_id in enumerate(result_ids):
                    chunks.append({
                        "chunk_id": chunk_id,
                        "text": results["documents"][i][j] if "documents" in results else "",
                        "metadata": results["metadatas"][i][j] if "metadatas" in results else {}
                    })
                    
        return chunks
    except Exception as e:
        logger.error(f"Error getting document chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-db/stats", response_model=dict)
async def get_vector_db_stats():
    """
    Get vector database statistics
    
    Returns:
        dict: Vector database statistics
    """
    try:
        stats = vector_db.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting vector DB stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
    
    # Delete document chunks from vector DB
    pdf_service.delete_document_chunks(document_id)
    
    # Delete document from database
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


