from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from logging import getLogger

logger = getLogger(__name__)


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

    @abstractmethod
    def get_indexed_ids(self, vectorstore_wrapper, collection_suffix: Optional[str] = '') -> List[str]:
        """Get all indexed document IDs from vectorstore"""
        pass

    @abstractmethod
    def clean_collection(self, vectorstore_wrapper, collection_suffix: str = ''):
        """Clean the vectorstore collection by deleting all indexed data."""
        pass

    @abstractmethod
    def get_indexed_data(self, vectorstore_wrapper):
        """Get all indexed data from vectorstore for non-code content"""
        pass

    @abstractmethod
    def get_code_indexed_data(self, vectorstore_wrapper, collection_suffix) -> Dict[str, Dict[str, Any]]:
        """Get all indexed data from vectorstore for code content"""
        pass

    @abstractmethod
    def add_to_collection(self, vectorstore_wrapper, entry_id, new_collection_value):
        """Add a new collection name to the metadata"""
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

    def list_collections(self, vectorstore_wrapper) -> str:
        from sqlalchemy import func
        from sqlalchemy.orm import Session

        store = vectorstore_wrapper.vectorstore
        try:
            with Session(store.session_maker.bind) as session:
                collections = (
                    session.query(
                        func.distinct(func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection'))
                    )
                    .filter(store.EmbeddingStore.cmetadata.isnot(None))
                    .all()
                )
                return [collection[0] for collection in collections if collection[0] is not None]
        except Exception as e:
            logger.error(f"Failed to get unique collections from PGVector: {str(e)}")
            return []

    def remove_collection(self, vectorstore_wrapper, collection_name: str):
        from sqlalchemy import text
        from sqlalchemy.orm import Session

        schema_name = vectorstore_wrapper.vectorstore.collection_name
        with Session(vectorstore_wrapper.vectorstore.session_maker.bind) as session:
            drop_schema_query = text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")
            session.execute(drop_schema_query)
            session.commit()
            logger.info(f"Schema '{schema_name}' has been dropped.")

    def get_indexed_ids(self, vectorstore_wrapper, collection_suffix: Optional[str] = '') -> List[str]:
        """Get all indexed document IDs from PGVector"""
        from sqlalchemy.orm import Session
        from sqlalchemy import func

        store = vectorstore_wrapper.vectorstore
        try:
            with Session(store.session_maker.bind) as session:
                # Start building the query
                query = session.query(store.EmbeddingStore.id)
                # Apply filter only if collection_suffix is provided
                if collection_suffix:
                    query = query.filter(
                        func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection') == collection_suffix
                    )
                ids = query.all()
                return [str(id_tuple[0]) for id_tuple in ids]
        except Exception as e:
            logger.error(f"Failed to get indexed IDs from PGVector: {str(e)}")
            return []

    def clean_collection(self, vectorstore_wrapper, collection_suffix: str = ''):
        """Clean the vectorstore collection by deleting all indexed data."""
        # This logic deletes all data from the vectorstore collection without removal of collection.
        # Collection itself remains available for future indexing.
        vectorstore_wrapper.vectorstore.delete(ids=self.get_indexed_ids(vectorstore_wrapper, collection_suffix))

    def is_vectorstore_type(self, vectorstore) -> bool:
        """Check if the vectorstore is a PGVector store."""
        return hasattr(vectorstore, 'session_maker') and hasattr(vectorstore, 'EmbeddingStore')

    def get_indexed_data(self, vectorstore_wrapper, collection_suffix: str)-> Dict[str, Dict[str, Any]]:
        """Get all indexed data from PGVector for non-code content per collection_suffix."""
        from sqlalchemy.orm import Session
        from sqlalchemy import func
        from ...runtime.utils.utils import IndexerKeywords

        result = {}
        try:
            vectorstore_wrapper._log_data("Retrieving already indexed data from PGVector vectorstore",
                           tool_name="get_indexed_data")
            store = vectorstore_wrapper.vectorstore
            with Session(store.session_maker.bind) as session:
                docs = session.query(
                    store.EmbeddingStore.id,
                    store.EmbeddingStore.document,
                    store.EmbeddingStore.cmetadata
                ).filter(
                    func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection') == collection_suffix
                ).all()

            # Process the retrieved data
            for doc in docs:
                db_id = doc.id
                meta = doc.cmetadata or {}

                # Get document id from metadata
                doc_id = str(meta.get('id', db_id))
                dependent_docs = meta.get(IndexerKeywords.DEPENDENT_DOCS.value, [])
                if dependent_docs:
                    dependent_docs = [d.strip() for d in dependent_docs.split(';') if d.strip()]
                parent_id = meta.get(IndexerKeywords.PARENT.value, -1)

                chunk_id = meta.get('chunk_id')
                if doc_id in result and chunk_id:
                    # If document with the same id already saved, add db_id for current one as chunk
                    result[doc_id]['all_chunks'].append(db_id)
                else:
                    result[doc_id] = {
                        'metadata': meta,
                        'id': db_id,
                        'all_chunks': [db_id],
                        IndexerKeywords.DEPENDENT_DOCS.value: dependent_docs,
                        IndexerKeywords.PARENT.value: parent_id
                    }

        except Exception as e:
            logger.error(f"Failed to get indexed data from PGVector: {str(e)}. Continuing with empty index.")

        return result

    def get_code_indexed_data(self, vectorstore_wrapper, collection_suffix: str) -> Dict[str, Dict[str, Any]]:
        """Get all indexed code data from PGVector per collection suffix."""
        from sqlalchemy.orm import Session
        from sqlalchemy import func

        result = {}
        try:
            vectorstore_wrapper._log_data("Retrieving already indexed code data from PGVector vectorstore",
                           tool_name="index_code_data")
            store = vectorstore_wrapper.vectorstore
            with (Session(store.session_maker.bind) as session):
                docs = session.query(
                    store.EmbeddingStore.id,
                    store.EmbeddingStore.cmetadata
                ).filter(
                    func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection') == collection_suffix
                ).all()

            for db_id, meta in docs:
                filename = meta.get('filename')
                commit_hash = meta.get('commit_hash')
                if not filename:
                    continue
                if filename not in result:
                    result[filename] = {
                        'metadata': meta,
                        'commit_hashes': [],
                        'ids': []
                    }
                if commit_hash is not None:
                    result[filename]['commit_hashes'].append(commit_hash)
                result[filename]['ids'].append(db_id)
        except Exception as e:
            logger.error(f"Failed to get indexed code data from PGVector: {str(e)}. Continuing with empty index.")
        return result

    def add_to_collection(self, vectorstore_wrapper, entry_id, new_collection_value):
        """Add a new collection name to the `collection` key in the `metadata` column."""
        from sqlalchemy import func
        from sqlalchemy.orm import Session

        store = vectorstore_wrapper.vectorstore
        try:
            with Session(store.session_maker.bind) as session:
                # Query the current value of the `collection` key
                current_collection_query = session.query(
                    func.jsonb_extract_path_text(store.EmbeddingStore.cmetadata, 'collection')
                ).filter(store.EmbeddingStore.id == entry_id).scalar()

                # If the `collection` key is NULL or doesn't contain the new value, update it
                if current_collection_query is None:
                    # If `collection` is NULL, initialize it with the new value
                    session.query(store.EmbeddingStore).filter(
                        store.EmbeddingStore.id == entry_id
                    ).update(
                        {
                            store.EmbeddingStore.cmetadata: func.jsonb_set(
                                func.coalesce(store.EmbeddingStore.cmetadata, '{}'),
                                '{collection}',  # Path to the `collection` key
                                f'"{new_collection_value}"',  # New value for the `collection` key
                                True  # Create the key if it doesn't exist
                            )
                        }
                    )
                elif new_collection_value not in current_collection_query.split(";"):
                    # If `collection` exists but doesn't contain the new value, append it
                    updated_collection_value = f"{current_collection_query};{new_collection_value}"
                    session.query(store.EmbeddingStore).filter(
                        store.EmbeddingStore.id == entry_id
                    ).update(
                        {
                            store.EmbeddingStore.cmetadata: func.jsonb_set(
                                store.EmbeddingStore.cmetadata,
                                '{collection}',  # Path to the `collection` key
                                f'"{updated_collection_value}"',  # Concatenated value as a valid JSON string
                                True  # Create the key if it doesn't exist
                            )
                        }
                    )

                session.commit()
                logger.info(f"Successfully updated collection for entry ID {entry_id}.")
        except Exception as e:
            logger.error(f"Failed to update collection for entry ID {entry_id}: {str(e)}")


class ChromaAdapter(VectorStoreAdapter):
    """Adapter for Chroma database operations."""

    def get_vectorstore_params(self, collection_name: str, connection_string: Optional[str] = None) -> Dict[str, Any]:
        return {
            "collection_name": collection_name,
            "persist_directory": "./indexer_db"
        }

    def list_collections(self, vectorstore_wrapper) -> str:
        vector_client = vectorstore_wrapper.vectorstore._client
        return ','.join([collection.name for collection in vector_client.list_collections()])

    def remove_collection(self, vectorstore_wrapper, collection_name: str):
        vectorstore_wrapper.vectorstore.delete_collection()

    def get_indexed_ids(self, vectorstore_wrapper, collection_suffix: Optional[str] = '') -> List[str]:
        """Get all indexed document IDs from Chroma"""
        try:
            data = vectorstore_wrapper.vectorstore.get(include=[])  # Only get IDs, no metadata
            return data.get('ids', [])
        except Exception as e:
            logger.error(f"Failed to get indexed IDs from Chroma: {str(e)}")
            return []

    def clean_collection(self, vectorstore_wrapper, collection_suffix: str = ''):
        """Clean the vectorstore collection by deleting all indexed data."""
        vectorstore_wrapper.vectorstore.delete(ids=self.get_indexed_ids(vectorstore_wrapper, collection_suffix))

    def get_indexed_data(self, vectorstore_wrapper):
        """Get all indexed data from Chroma for non-code content"""
        from ...runtime.utils.utils import IndexerKeywords

        result = {}
        try:
            vectorstore_wrapper._log_data("Retrieving already indexed data from Chroma vectorstore",
                           tool_name="get_indexed_data")
            data = vectorstore_wrapper.vectorstore.get(include=['metadatas'])

            # Re-structure data to be more usable
            for meta, db_id in zip(data['metadatas'], data['ids']):
                # Get document id from metadata
                doc_id = str(meta['id'])
                dependent_docs = meta.get(IndexerKeywords.DEPENDENT_DOCS.value, [])
                if dependent_docs:
                    dependent_docs = [d.strip() for d in dependent_docs.split(';') if d.strip()]
                parent_id = meta.get(IndexerKeywords.PARENT.value, -1)

                chunk_id = meta.get('chunk_id')
                if doc_id in result and chunk_id:
                    # If document with the same id already saved, add db_id for current one as chunk
                    result[doc_id]['all_chunks'].append(db_id)
                else:
                    result[doc_id] = {
                        'metadata': meta,
                        'id': db_id,
                        'all_chunks': [db_id],
                        IndexerKeywords.DEPENDENT_DOCS.value: dependent_docs,
                        IndexerKeywords.PARENT.value: parent_id
                    }
        except Exception as e:
            logger.error(f"Failed to get indexed data from Chroma: {str(e)}. Continuing with empty index.")

        return result

    def get_code_indexed_data(self, vectorstore_wrapper, collection_suffix) -> Dict[str, Dict[str, Any]]:
        """Get all indexed code data from Chroma."""
        result = {}
        try:
            vectorstore_wrapper._log_data("Retrieving already indexed code data from Chroma vectorstore",
                           tool_name="index_code_data")
            data = vectorstore_wrapper.vectorstore.get(include=['metadatas'])
            for meta, db_id in zip(data['metadatas'], data['ids']):
                filename = meta.get('filename')
                commit_hash = meta.get('commit_hash')
                if not filename:
                    continue
                if filename not in result:
                    result[filename] = {
                        'commit_hashes': [],
                        'ids': []
                    }
                if commit_hash is not None:
                    result[filename]['commit_hashes'].append(commit_hash)
                result[filename]['ids'].append(db_id)
        except Exception as e:
            logger.error(f"Failed to get indexed code data from Chroma: {str(e)}. Continuing with empty index.")
        return result

    def add_to_collection(self, vectorstore_wrapper, entry_id, new_collection_value):
        """Add a new collection name to the metadata - Chroma implementation"""
        # For Chroma, we would need to update the metadata through vectorstore operations
        # This is a simplified implementation - in practice, you might need more complex logic
        logger.warning("add_to_collection for Chroma is not fully implemented yet")


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
