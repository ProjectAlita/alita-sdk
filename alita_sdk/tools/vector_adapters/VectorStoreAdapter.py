from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class VectorStoreAdapter(ABC):
    """Abstract base class for vector store adapters."""

    @abstractmethod
    def get_vectorstore_params(self, collection_name: str, connection_string: Optional[str] = None) -> Dict[str, Any]:
        """Get vector store specific parameters."""
        pass

    @abstractmethod
    def list_collections(self, vectorstore_wrapper) -> str:
        """List all collections in the vector store."""
        pass

    @abstractmethod
    def remove_collection(self, vectorstore_wrapper, collection_name: str):
        """Remove a collection from the vector store."""
        pass


class PGVectorAdapter(VectorStoreAdapter):
    """Adapter for PGVector database operations."""

    def get_vectorstore_params(self, collection_name: str, connection_string: Optional[str] = None) -> Dict[str, Any]:
        return {
            "use_jsonb": True,
            "collection_name": collection_name,
            "create_extension": True,
            "alita_sdk_options": {
                "target_schema": collection_name,
            },
            "connection_string": connection_string
        }

    def list_collections(self, vectorstore_wrapper, collection_name) -> str:
        from sqlalchemy import text
        from sqlalchemy.orm import Session

        with Session(vectorstore_wrapper.vectorstore.session_maker.bind) as session:
            get_collections = text(f"""
                 SELECT table_schema
                 FROM information_schema.columns
                 WHERE udt_name = 'vector'
                   AND table_schema LIKE '%{collection_name}%';
            """)
            result = session.execute(get_collections)
            docs = result.fetchall()
        return str(docs)

    def remove_collection(self, vectorstore_wrapper, collection_name: str):
        vectorstore_wrapper._remove_collection()


class ChromaAdapter(VectorStoreAdapter):
    """Adapter for Chroma database operations."""

    def get_vectorstore_params(self, collection_name: str, connection_string: Optional[str] = None) -> Dict[str, Any]:
        return {
            "collection_name": collection_name,
            "persist_directory": "./indexer_db"
        }

    def list_collections(self, vectorstore_wrapper) -> str:
        vector_client = vectorstore_wrapper.vectoradapter.vectorstore._client
        return ','.join([collection.name for collection in vector_client.list_collections()])

    def remove_collection(self, vectorstore_wrapper, collection_name: str):
        vectorstore_wrapper.vectoradapter.vectorstore.delete_collection()


class VectorStoreAdapterFactory:
    """Factory for creating vector store adapters."""

    _adapters = {
        'PGVector': PGVectorAdapter,
        'Chroma': ChromaAdapter,
    }

    @classmethod
    def create_adapter(cls, vectorstore_type: str) -> VectorStoreAdapter:
        adapter_class = cls._adapters.get(vectorstore_type)
        if not adapter_class:
            raise ValueError(f"Unsupported vectorstore type: {vectorstore_type}")
        return adapter_class()

    @classmethod
    def register_adapter(cls, vectorstore_type: str, adapter_class: type):
        """Register a new adapter for a vector store type."""
        cls._adapters[vectorstore_type] = adapter_class
