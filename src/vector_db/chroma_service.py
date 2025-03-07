import os
from typing import List, Dict, Any, Optional
from uuid import UUID

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from src.core.config import config
from src.core.logger import logger


class ChromaService:
    def __init__(self):
        # Get config from YAML file
        self.persist_directory = config.get("vector_db.persist_dir", "./data/chroma_db")
        self.collection_name = config.get("vector_db.collection_name", "document_chunks")
        self.embedding_model = config.get("vector_db.embedding_model", "all-MiniLM-L6-v2")
        self.embedding_function_name = config.get("vector_db.embedding_function", "sentence_transformer")
        
        # Get OpenAI config if needed
        self.openai_api_key = config.get("openai.api_key", os.environ.get("OPENAI_API_KEY"))
        self.openai_model = config.get("openai.embedding_model", "text-embedding-ada-002")
        
        # Client and collection references
        self.client = None
        self.collection = None
        self.embedding_function = None
        
        # Initialize connection
        self._initialize()
    
    def _initialize(self):
        """Initialize Chroma client and create collection if it doesn't exist"""
        try:
            logger.info(f"Initializing ChromaDB with persist directory: {self.persist_directory}")
            
            # Initialize client with settings from config
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=config.get("vector_db.anonymized_telemetry", False),
                    allow_reset=config.get("vector_db.allow_reset", True)
                )
            )
            
            # Set up embedding function based on config
            if self.embedding_function_name == "openai":
                if not self.openai_api_key:
                    logger.warning("OpenAI API key not found, falling back to SentenceTransformer")
                    self.embedding_function_name = "sentence_transformer"
                else:
                    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                        api_key=self.openai_api_key,
                        model_name=self.openai_model
                    )
                    self.embedding_function = openai_ef
                    logger.info(f"Using OpenAI embedding model: {self.openai_model}")
            
            # Default to SentenceTransformer
            if self.embedding_function_name != "openai" or self.embedding_function is None:
                self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.embedding_model
                )
                logger.info(f"Using SentenceTransformer embedding model: {self.embedding_model}")
            
            # Get or create collection - FIX HERE
            try:
                # Try to get existing collection
                logger.info(f"Trying to get existing collection: {self.collection_name}")
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Connected to existing collection: {self.collection_name}")
            except Exception as e:
                # If collection doesn't exist or any other error, create a new one
                logger.info(f"Collection not found or error: {str(e)}. Creating new collection: {self.collection_name}")
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
            logger.info("ChromaDB initialization complete")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {str(e)}")
            raise
    
    def add_chunks(
        self, 
        document_id: UUID, 
        chunks: List[str], 
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Add document chunks to the vector database
        
        Args:
            document_id: UUID of the document
            chunks: List of text chunks
            metadatas: List of metadata dictionaries for each chunk
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not chunks:
                logger.warning(f"No chunks provided for document {document_id}")
                return False

            # Generate IDs for chunks
            chunk_ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            
            # Prepare metadata if not provided
            if not metadatas:
                metadatas = [{"document_id": str(document_id), "chunk_index": i} for i in range(len(chunks))]
            else:
                # Ensure document_id is in each metadata dict
                for i, meta in enumerate(metadatas):
                    meta["document_id"] = str(document_id)
                    meta["chunk_index"] = i
            
            # Add chunks to collection
            self.collection.add(
                ids=chunk_ids,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(chunks)} chunks for document {document_id} to ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Error adding chunks to ChromaDB: {str(e)}")
            return False
    
    def search(
        self, 
        query: str, 
        n_results: int = 5, 
        document_id: Optional[UUID] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar chunks
        
        Args:
            query: Query string
            n_results: Number of results to return
            document_id: Optional document ID to filter results
            filter_dict: Additional filters to apply
            
        Returns:
            Dict containing search results
        """
        try:
            # Prepare filter
            where_filter = {}
            if filter_dict:
                where_filter.update(filter_dict)
            if document_id:
                where_filter["document_id"] = str(document_id)
            
            # Use empty filter if none specified
            where_clause = where_filter if where_filter else None
            
            # Execute search
            if not query.strip():
                # If query is empty, just get documents by filter
                results = self.collection.get(
                    where=where_clause,
                    limit=n_results
                )
            else:
                # Normal vector search
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_clause
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {str(e)}")
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}
    
    def delete_document(self, document_id: UUID) -> bool:
        """
        Delete all chunks for a document
        
        Args:
            document_id: Document ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.collection.delete(
                where={"document_id": str(document_id)}
            )
            logger.info(f"Deleted all chunks for document {document_id} from ChromaDB")
            return True
        except Exception as e:
            logger.error(f"Error deleting document chunks from ChromaDB: {str(e)}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection
        
        Returns:
            Dict with collection statistics
        """
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_chunks_count": count,
                "embedding_function": self.embedding_function_name,
                "embedding_model": self.embedding_model if self.embedding_function_name != "openai" else self.openai_model
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}