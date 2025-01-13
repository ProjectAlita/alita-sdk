# pylint: disable=C0103

""" Multiple vectorstore support tools """

from ..interfaces.llm_processor import add_documents
from .quota import quota_check, sqlite_vacuum
from . import log


class VectorAdapter:
    """ Vectorstore adapter """

    def __init__(self, vectorstore, embeddings=None, quota_params=None):
        self._vectorstore = vectorstore
        self._embeddings = embeddings
        self._quota_params = quota_params
        #
        self._vs_cls_name = self._vectorstore.__class__.__name__

    @property
    def vectorstore(self):
        """ Get vectorstore """
        return self._vectorstore

    @property
    def embeddings(self):
        """ Get embeddings if present """
        result = self._vectorstore.embeddings
        if result is None:
            return self._embeddings
        return result

    def persist(self):
        """ Save/sync/checkpoint vectorstore (if needed/supported) """
        if self._vs_cls_name == "Chroma":
            # Note: no version check (< 0.4.0) here
            self._vectorstore.persist()

    def vacuum(self):
        """ Optimize space usage (trim; if supported) """
        if self._vs_cls_name == "Chroma":
            sqlite_vacuum(
                params=self._quota_params
            )

    def quota_check(self, enforce=True, tag="Quota", verbose=False):
        """ Check used space size (if supported) """
        if self._vs_cls_name == "Chroma":
            return quota_check(
                params=self._quota_params,
                enforce=enforce,
                tag=tag,
                verbose=verbose,
            )
        #
        return {"ok": True}

    def delete_dataset(self, dataset):
        """ Delete dataset documents """
        if self._vs_cls_name == "Chroma":
            self._vectorstore._collection.delete(where={"dataset": dataset})  # pylint: disable=W0212
        #
        elif self._vs_cls_name == "PGVector":
            self._pgvector_delete_by_filter(where={"dataset": dataset})
        #
        else:
            raise RuntimeError(f"Unsupported vectorstore: {self._vs_cls_name}")

    def delete_library(self, library):
        """ Delete datasource (library) documents """
        if self._vs_cls_name == "Chroma":
            if (library == self._vectorstore._collection.name):  # pylint: disable=W0212
                self._vectorstore._client.delete_collection(self._vectorstore._collection.name)  # pylint: disable=W0212
            else:
                self._vectorstore._collection.delete(where={"library": library})  # pylint: disable=W0212
        #
        elif self._vs_cls_name == "PGVector":
            if library == self._vectorstore.collection_name:
                self._vectorstore.delete_collection()
            else:
                self._pgvector_delete_by_filter(where={"library": library})
        #
        else:
            raise RuntimeError(f"Unsupported vectorstore: {self._vs_cls_name}")

    def get_data(self, where, include):
        """ Get data (documents, metadatas) from store """
        if self._vs_cls_name == "Chroma":  # pylint: disable=R1705
            return self._vectorstore.get(
                where=where,
                include=include,
            )
        #
        elif self._vs_cls_name == "PGVector":
            return self._pgvector_get_data(
                where=where,
                include=include,
            )
        #
        else:
            raise RuntimeError(f"Unsupported vectorstore: {self._vs_cls_name}")

    def get_existing_documents(self, dataset, library):
        """ Get existing documents and their hashes from store """
        data = self.get_data_efficient(
            where={"$and": [
                {"dataset": dataset},
                {"library": library},
            ]},
            include=["metadatas"]
        )

        existing_docs = {}
        for metadata in data["metadatas"]:
            doc_hash = metadata.get("chunk_hash")
            source = metadata.get("source")
            key = (doc_hash, source)
            if doc_hash and source:
                existing_docs[key] = {
                    "id": metadata['id'],
                }
        return existing_docs

    def batch_add_documents(self, documents, batch_size=100):
        """Add documents in batches"""
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            add_documents(vectorstore=self.vectorstore, documents=batch)

    def batch_delete_documents(self, dataset, doc_hashes, batch_size=100):
        """Delete documents in batches by their hashes"""
        if not doc_hashes:
            return
        
        for i in range(0, len(doc_hashes), batch_size):
            batch = doc_hashes[i:i + batch_size]
            where_clause = {
                "$and": [
                    {"dataset": dataset},
                    {"chunk_hash": {"$in": batch}}
                ]
            }
            if self._vs_cls_name == "Chroma":
                self._vectorstore._collection.delete(where=where_clause)  # pylint: disable=W0212
            elif self._vs_cls_name == "PGVector":
                self._pgvector_delete_by_filter(where=where_clause)

    def batch_delete_by_ids(self, ids):
        """Optimized batch deletion"""
        if not ids:
            return
        
        if self._vs_cls_name == "Chroma":
            # Use single deletion operation
            self._vectorstore._collection.delete(ids=ids)
        elif self._vs_cls_name == "PGVector":
            self._pgvector_delete_by_ids(ids)

    def _pgvector_get_data(self, where, include):
        # Adapted from langchain_community/vectorstores/pgvector.py
        from sqlalchemy.orm import Session  # pylint: disable=C0415,E0401
        #
        if not isinstance(include, list):
            raise ValueError("Unsupported include type")
        #
        supported_includes = ["documents", "metadatas"]
        for item in include:
            if item not in supported_includes:
                raise ValueError(f"Unsupported include value: {item}")
        #
        data_result = {}
        #
        if "documents" in include:
            data_result["documents"] = []
        #
        if "metadatas" in include:
            data_result["metadatas"] = []
        #
        with Session(self._vectorstore._bind) as session:  # pylint: disable=W0212
            collection = self._vectorstore.get_collection(session)
            if not collection:
                raise ValueError("Collection not found")
            #
            filter_by = [self._vectorstore.EmbeddingStore.collection_id == collection.uuid]
            if where:
                if self._vectorstore.use_jsonb:
                    filter_clauses = self._vectorstore._create_filter_clause(where)  # pylint: disable=W0212
                    #
                    if filter_clauses is not None:
                        filter_by.append(filter_clauses)
                    #
                    log.debug("PG (JSONB) filter clauses: %s", filter_by)
                    for idx, clause in enumerate(filter_by):
                        log.debug("- %d: %s", idx, str(clause))
                else:
                    # --- FIXME: support converting 'new' filters
                    # to '_create_filter_clause_deprecated' format
                    if isinstance(where, dict) and len(where) == 1 and "$and" in where:
                        where_fixed = {}
                        #
                        for where_item in where["$and"]:
                            where_fixed.update(where_item)
                        #
                        filter_clauses = self._vectorstore._create_filter_clause_json_deprecated(where_fixed)  # pylint: disable=W0212,C0301
                        #
                        filter_by.extend(filter_clauses)
                    else:  # just pass as-is
                        # Old way of doing things
                        filter_clauses = self._vectorstore._create_filter_clause_json_deprecated(where)  # pylint: disable=W0212,C0301
                        #
                        filter_by.extend(filter_clauses)
                    #
                    log.debug("PG (JSON) filter clauses: %s", filter_by)
                    for idx, clause in enumerate(filter_by):
                        log.debug("- %d: %s", idx, str(clause))
            #
            _type = self._vectorstore.EmbeddingStore
            #
            query = session.query(self._vectorstore.EmbeddingStore).filter(*filter_by)
            #
            log.debug("PGV query: %s", str(query))
            #
            results = query.all()
            #
            for result in results:
                data_result["documents"].append(result.document)
                data_result["metadatas"].append(result.cmetadata)
        #
        return data_result

    def _pgvector_delete_by_ids(self, ids):
        """Optimized batch deletion by IDs for PGVector"""
        from sqlalchemy.orm import Session  # pylint: disable=C0415,E0401
        
        with Session(self._vectorstore._bind) as session:  # pylint: disable=W0212
            # Single query to delete all matching documents
            session.query(self._vectorstore.EmbeddingStore).filter(
                self._vectorstore.EmbeddingStore.id.in_(ids)
            ).delete(synchronize_session=False)
            session.commit()

    def _pgvector_delete_by_filter(self, where):
        """Optimized filter-based deletion for PGVector"""
        from sqlalchemy.orm import Session  # pylint: disable=C0415,E0401
        
        with Session(self._vectorstore._bind) as session:  # pylint: disable=W0212
            collection = self._vectorstore.get_collection(session)
            if not collection:
                raise ValueError("Collection not found")
            
            filter_by = [self._vectorstore.EmbeddingStore.collection_id == collection.uuid]
            if where:
                if self._vectorstore.use_jsonb:
                    filter_clauses = self._vectorstore._create_filter_clause(where)  # pylint: disable=W0212
                    if filter_clauses is not None:
                        filter_by.append(filter_clauses)
                else:
                    filter_clauses = self._vectorstore._create_filter_clause_json_deprecated(where)  # pylint: disable=W0212
                    filter_by.extend(filter_clauses)
            
            # Single query to delete all matching documents
            session.query(self._vectorstore.EmbeddingStore).filter(
                *filter_by
            ).delete(synchronize_session=False)
            session.commit()

    def get_data_efficient(self, where, include):
        """Get data with minimal DB load"""
        if self._vs_cls_name == "Chroma":
            # Use direct collection access for Chroma
            return self._vectorstore._collection.get(  # pylint: disable=W0212
                where=where,
                include=include
            )
        elif self._vs_cls_name == "PGVector":
            # Optimize PGVector query
            return self._pgvector_get_data_optimized(where, include)
        else:
            return self.get_data(where, include)

    def _pgvector_get_data_optimized(self, where, include):
        """
        Optimized data retrieval for PGVector using a single query.
        Fetches both documents and metadatas in one database call.
        """
        from sqlalchemy.orm import Session
        from sqlalchemy import select, and_
        #
        if not isinstance(include, list):
            raise ValueError("Unsupported include type")
        #
        supported_includes = ["documents", "metadatas"]
        for item in include:
            if item not in supported_includes:
                raise ValueError(f"Unsupported include value: {item}")
        #
        data_result = {}
        #
        if "documents" in include:
            data_result["documents"] = []
        #
        if "metadatas" in include:
            data_result["metadatas"] = []
        
        with Session(self._vectorstore._bind) as session:
            collection = self._vectorstore.get_collection(session)
            if not collection:
                raise ValueError("Collection not found")
                
            stmt = select(self._vectorstore.EmbeddingStore).where(
                self._vectorstore.EmbeddingStore.collection_id == collection.uuid
            )

            if where:
                if self._vectorstore.use_jsonb:
                    filter_clause = self._vectorstore._create_filter_clause(where)
                    if filter_clause is not None:
                        stmt = stmt.where(filter_clause)
                else:
                    filter_clauses = self._vectorstore._create_filter_clause_json_deprecated(where)
                    stmt = stmt.where(and_(*filter_clauses))

            # Execute optimized query
            results = session.execute(stmt).fetchall()
            
            # Format results efficiently
            for result in results:
                data_result["documents"].append(result.document)
                data_result["metadatas"].append(result.cmetadata)
            return data_result
