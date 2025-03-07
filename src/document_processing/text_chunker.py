import re
from typing import List, Dict, Any, Tuple, Optional

from src.core.config import config
from src.core.logger import logger


class TextChunker:
    """Service for chunking text documents into smaller pieces for vector storage"""
    
    def __init__(self):
        # Load config from YAML
        self.chunk_size = int(config.get("document_processing.chunk_size", 1000))
        self.chunk_overlap = int(config.get("document_processing.chunk_overlap", 200))
        self.separator = str(config.get("document_processing.separator", "\n"))
        self.max_chunks = int(config.get("document_processing.max_chunks", 1000))  # Safety limit
        
        logger.info(f"Text Chunker initialized with chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")
    
    def chunk_text(
        self, 
        text: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Split text into chunks with optional overlap
        
        Args:
            text: Text to split into chunks
            document_id: Optional document ID to include in metadata
            metadata: Optional metadata to include with each chunk
            
        Returns:
            Tuple containing:
                - List of text chunks
                - List of metadata dictionaries for each chunk
        """
        if not text:
            logger.warning("Received empty text for chunking")
            return [], []
            
        try:
            logger.info(f"Chunking text of length {len(text)} with chunk size {self.chunk_size}")
            
            # Basic preprocessing to normalize line breaks
            text = re.sub(r'\r\n', '\n', text)
            
            # Split by separator
            splits = text.split(self.separator)
            
            chunks = []
            chunks_metadata = []
            current_chunk = []
            current_length = 0
            
            # Create chunks
            for split in splits:
                # Skip empty splits
                if not split.strip():
                    continue
                    
                # If adding this split would exceed chunk size, finish the current chunk
                if current_length + len(split) > self.chunk_size and current_length > 0:
                    # Save current chunk
                    chunk_text = self.separator.join(current_chunk)
                    chunks.append(chunk_text)
                    
                    # Create metadata for this chunk
                    chunk_meta = {"length": len(chunk_text)}
                    if metadata:
                        chunk_meta.update(metadata)
                    if document_id:
                        chunk_meta["document_id"] = document_id
                    chunks_metadata.append(chunk_meta)
                    
                    # Keep overlap for next chunk if overlap is configured
                    if self.chunk_overlap > 0:
                        # Find the splits that should be kept for overlap
                        overlap_length = 0
                        overlap_splits = []
                        
                        # Work backwards through current_chunk to find splits for overlap
                        for item in reversed(current_chunk):
                            if overlap_length + len(item) <= self.chunk_overlap:
                                overlap_splits.insert(0, item)
                                overlap_length += len(item) + len(self.separator)
                            else:
                                break
                                
                        # Reset with overlap content
                        current_chunk = overlap_splits
                        current_length = overlap_length
                    else:
                        # No overlap, start fresh
                        current_chunk = []
                        current_length = 0
                
                # Add the current split to the chunk
                current_chunk.append(split)
                current_length += len(split) + len(self.separator)
                
                # Check if we've hit the max chunks limit
                if len(chunks) >= self.max_chunks:
                    logger.warning(f"Reached maximum chunk limit of {self.max_chunks}")
                    break
            
            # Don't forget the last chunk if there's anything left
            if current_chunk:
                chunk_text = self.separator.join(current_chunk)
                chunks.append(chunk_text)
                
                # Create metadata for the last chunk
                chunk_meta = {"length": len(chunk_text)}
                if metadata:
                    chunk_meta.update(metadata)
                if document_id:
                    chunk_meta["document_id"] = document_id
                chunks_metadata.append(chunk_meta)
            
            logger.info(f"Created {len(chunks)} chunks from text")
            return chunks, chunks_metadata
            
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            return [], []
    
    def create_chunk_with_context(
        self,
        chunk_text: str,
        source_text: str,
        window_size: Optional[int] = None
    ) -> str:
        """
        Create a chunk with additional context from source text
        
        Args:
            chunk_text: The original chunk text
            source_text: The source text to extract context from
            window_size: Size of context window on each side (will use config if None)
            
        Returns:
            Chunk with added context
        """
        try:
            # Get window size from config if not specified
            if window_size is None:
                window_size = config.get("document_processing.context_window_size", 100)
                
            # Find position of chunk in source text
            chunk_start = source_text.find(chunk_text)
            
            if chunk_start == -1:
                logger.warning("Could not find chunk in source text for context")
                return chunk_text
                
            chunk_end = chunk_start + len(chunk_text)
            
            # Get context before and after
            context_start = max(0, chunk_start - window_size)
            context_end = min(len(source_text), chunk_end + window_size)
            
            # Extract text with context
            text_with_context = source_text[context_start:context_end]
            
            return text_with_context
            
        except Exception as e:
            logger.error(f"Error creating chunk with context: {str(e)}")
            return chunk_text