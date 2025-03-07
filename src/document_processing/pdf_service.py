import os
from pathlib import Path
import traceback
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from uuid import UUID

import PyPDF2
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError
from sqlalchemy.orm import Session

from src.core.logger import logger
from src.core.config import config
from src.database.model import Document, ProcessingStatus
from src.document_processing.text_chunker import TextChunker
from src.vector_db.chroma_service import ChromaService


class PDFService:
    def __init__(self):
        # Get configs from YAML file
        self.extraction_timeout = config.get("document_processing.extraction_timeout", 300)
        self.auto_chunk = config.get("document_processing.auto_chunk", True)
        self.chunking_strategy = config.get("document_processing.chunking_strategy", "text_chunker")
        
        # Initialize services
        self.text_chunker = TextChunker()
        self.vector_db = ChromaService()
        
        logger.info(f"PDFService initialized with auto_chunk={self.auto_chunk}, strategy={self.chunking_strategy}")

    def validate_pdf(self, file_path: Path) -> tuple[bool, str | None]:
        """
        Validate if the file is a pdf file

        Args:
            file_path (Path): path to the file

        Returns:
            bool: True if the file is a pdf file, False otherwise
        """
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False, f"File not found: {file_path}"

        if file_path.suffix.lower() != ".pdf":
            logger.error(f"File is not a PDF: {file_path}")
            return False, f"File is not a PDF: {file_path}"

        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if len(pdf_reader.pages) == 0:
                    logger.error(f"PDF file has no pages: {file_path}")
                    return False, "PDF file has no pages"

            logger.info(f"Successfully validated PDF: {file_path}")
            return True, None
        except Exception as e:
            error_msg = f"Invalid PDF file: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def extract_text(self, file_path: Path) -> tuple[str | None, str | None]:
        """
        Extract text from a PDF file

        Args:
            file_path: Path to the PDF file

        Returns:
            Extracted text or None if failed, Error message or None if successful
        """
        try:
            logger.info(f"Extracting text from {file_path}")

            # Try with PDFMiner first
            extracted_text = pdfminer_extract_text(file_path)

            # If PDFMiner fails, try PyPDF2
            if not extracted_text or len(extracted_text.strip()) == 0:
                logger.info(
                    f"PDFMiner extraction failed, trying PyPDF2 for {file_path}"
                )
                extracted_text = self._extract_with_pypdf2(file_path)

            if not extracted_text or len(extracted_text.strip()) == 0:
                logger.warning(f"Could not extract text from PDF: {file_path}")
                return None, "Could not extract text from PDF"

            logger.info(
                f"Successfully extracted {len(extracted_text)} characters from {file_path}"
            )
            return extracted_text, None

        except PDFSyntaxError as e:
            error_msg = f"PDF syntax error: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error extracting text: {str(e)}"
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            logger.error(error_msg)
            return None, error_msg

    def _extract_with_pypdf2(self, file_path: Path) -> str | None:
        """
        Extract text from a PDF file using PyPDF2

        Args:
            file_path: Path to the PDF file
        Returns:
            Extracted text or None if extraction fails
        """
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                logger.debug(
                    f"Extracting text from {len(pdf_reader.pages)} pages with PyPDF2"
                )

                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    logger.debug(
                        f"Extracted page {i+1}/{len(pdf_reader.pages)} with {len(page_text)} characters"
                    )

                logger.info(
                    f"PyPDF2 extraction completed, extracted {len(text)} characters"
                )
                return text
        except Exception as e:
            logger.error(f"PyPDF2 extraction error: {str(e)}")
            return None
            
    # --- Chunking and Vector DB methods ---
    
    def process_chunks(self, document_id: UUID, text: str) -> Tuple[int, Optional[str]]:
        """
        Process text into chunks and store in vector database
        
        Args:
            document_id: ID of the document
            text: Text to process
            
        Returns:
            Tuple[int, Optional[str]]: Number of chunks processed and error message if any
        """
        try:
            logger.info(f"Processing document {document_id} for chunking")
            
            # Create document metadata
            metadata = {
                "document_id": str(document_id),
                "chunking_method": self.chunking_strategy,
                "chunking_size": self.text_chunker.chunk_size,
                "chunking_overlap": self.text_chunker.chunk_overlap,
                "processed_at": datetime.now().isoformat()
            }
            
            # Create chunks
            chunks, chunks_metadata = self.text_chunker.chunk_text(
                text=text,
                document_id=str(document_id),
                metadata=metadata
            )
            
            if not chunks:
                logger.warning(f"No chunks were generated for document {document_id}")
                return 0, "No chunks were generated"
                
            # Store chunks in vector database
            success = self.vector_db.add_chunks(
                document_id=document_id,
                chunks=chunks,
                metadatas=chunks_metadata
            )
            
            if not success:
                logger.error(f"Failed to store chunks in vector database for document {document_id}")
                return 0, "Failed to store chunks in vector database"
                
            logger.info(f"Successfully processed {len(chunks)} chunks for document {document_id}")
            return len(chunks), None
            
        except Exception as e:
            error_msg = f"Error processing chunks: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            return 0, error_msg
    
    # --- Database integration methods ---
    
    def create_document(self, db: Session, file_name: str, file_path: Optional[str] = None, file_size: Optional[int] = None) -> Document:
        """
        Create a new document in database
        
        Args:
            db: Database session
            file_name: Name of the file
            file_path: Path to the file
            file_size: Size of the file in bytes
            
        Returns:
            Document: Created document
        """
        document = Document(
            file_name=file_name,
            status=ProcessingStatus.PENDING
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Created document with ID {document.id} for file {file_name}")
        return document
    
    def save_extracted_text(self, db: Session, document_id: UUID, text: str) -> Document:
        """
        Save extracted text to an existing document
        
        Args:
            db: Database session
            document_id: ID of the document
            text: Extracted text
            
        Returns:
            Document: Updated document
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.extracted_text = text
            document.status = ProcessingStatus.COMPLETED
            document.processed_at = datetime.now()
            db.commit()
            db.refresh(document)
            logger.info(f"Saved extracted text ({len(text)} chars) to document {document_id}")
        else:
            logger.error(f"Document {document_id} not found")
        return document
    
    def set_document_error(self, db: Session, document_id: UUID, error_message: str) -> Document:
        """
        Set error status for a document
        
        Args:
            db: Database session
            document_id: ID of the document
            error_message: Error message
            
        Returns:
            Document: Updated document
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = ProcessingStatus.FAILED
            document.error_message = error_message
            document.processed_at = datetime.now()
            db.commit()
            db.refresh(document)
            logger.info(f"Set error status for document {document_id}: {error_message}")
        else:
            logger.error(f"Document {document_id} not found")
        return document
    
    def extract_and_save(self, db: Session, file_path: Path, file_name: str) -> Tuple[UUID, Optional[str], Optional[str]]:
        """
        Extract text from PDF and save to database
        
        Args:
            db: Database session
            file_path: Path to the PDF file
            file_name: Name of the file
            
        Returns:
            Tuple[UUID, Optional[str], Optional[str]]: 
                (document_id, extracted_text, error_message)
        """
        # Create document in database
        document = self.create_document(db, file_name)
        
        # Validate PDF
        is_valid, error_msg = self.validate_pdf(file_path)
        if not is_valid:
            self.set_document_error(db, document.id, error_msg)
            return document.id, None, error_msg
        
        # Extract text
        extracted_text, error_msg = self.extract_text(file_path)
        if error_msg or not extracted_text:
            error = error_msg or "Failed to extract text from document"
            self.set_document_error(db, document.id, error)
            return document.id, None, error
        
        # Save extracted text to database
        self.save_extracted_text(db, document.id, extracted_text)
        
        # Process chunks if auto_chunk is enabled
        if self.auto_chunk and extracted_text:
            chunk_count, chunk_error = self.process_chunks(document.id, extracted_text)
            if chunk_error:
                logger.warning(f"Error in chunking process: {chunk_error}")
                # We don't fail the whole process if chunking fails
        
        return document.id, extracted_text, None
    
    def delete_document_chunks(self, document_id: UUID) -> bool:
        """
        Delete all chunks for a document from vector database
        
        Args:
            document_id: Document ID
            
        Returns:
            bool: True if successful
        """
        try:
            success = self.vector_db.delete_document(document_id)
            if success:
                logger.info(f"Successfully deleted chunks for document {document_id}")
            else:
                logger.warning(f"Failed to delete chunks for document {document_id}")
            return success
        except Exception as e:
            logger.error(f"Error deleting chunks: {str(e)}")
            return False