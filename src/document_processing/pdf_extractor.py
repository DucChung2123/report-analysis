import os
from pathlib import Path
import traceback
import PyPDF2
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError
from src.core.logger import logger
from src.core.config import config

class PDFExtractor:
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
            
        if file_path.suffix.lower() != '.pdf':
            logger.error(f"File is not a PDF: {file_path}")
            return False, f"File is not a PDF: {file_path}"
        
        try:
            with open(file_path, 'rb') as file:
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
                logger.info(f"PDFMiner extraction failed, trying PyPDF2 for {file_path}")
                extracted_text = self._extract_with_pypdf2(file_path)
            
            if not extracted_text or len(extracted_text.strip()) == 0:
                logger.warning(f"Could not extract text from PDF: {file_path}")
                return None, "Could not extract text from PDF"
            
            logger.info(f"Successfully extracted {len(extracted_text)} characters from {file_path}")    
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
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                logger.debug(f"Extracting text from {len(pdf_reader.pages)} pages with PyPDF2")
                
                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    logger.debug(f"Extracted page {i+1}/{len(pdf_reader.pages)} with {len(page_text)} characters")
                
                logger.info(f"PyPDF2 extraction completed, extracted {len(text)} characters")
                return text
        except Exception as e:
            logger.error(f"PyPDF2 extraction error: {str(e)}")
            return None

# test
# if __name__ == "__main__":
#     pdf_extractor = PDFExtractor()
#     pdf_path = Path("data/DPR_Baocaothuongnien_2022.pdf")
#     is_valid, error_msg = pdf_extractor.validate_pdf(pdf_path)
#     if is_valid:
#         extracted_text, error_msg = pdf_extractor.extract_text(pdf_path)
#         if extracted_text:
#             print("successfully extracted text")
#     else:
#         print(error_msg)    
