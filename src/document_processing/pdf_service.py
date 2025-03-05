# src/document_processing/pdf_service.py
import os
from pathlib import Path
import traceback
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

import PyPDF2
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError
from sqlalchemy.orm import Session

from src.core.logger import logger
from src.core.config import config
from src.database.model import Document, ProcessingStatus


class PDFService:
    def __init__(self):
        self.extraction_time_out = config.get("document.etractor.timeout", 300)

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

            extracted_text = pdfminer_extract_text(file_path)

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
            
    # --- Database integration methods ---
    
    def create_document(self, db: Session, file_name: str) -> Document:
        """
        Create a new document in database
        
        Args:
            db: Database session
            file_name: Name of the file
            
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
        
        return document.id, extracted_text, None