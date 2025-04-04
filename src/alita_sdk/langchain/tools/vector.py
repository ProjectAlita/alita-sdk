# pylint: disable=C0103

""" Multiple vectorstore support tools """

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
        #
        if result is not None:
            return result
        #
        return self._embeddings

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
            if library == self._vectorstore._collection.name:  # pylint: disable=W0212
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
        try:
            engine_bind = self._vectorstore._bind  # pylint: disable=W0212
        except:  # pylint: disable=W0702
            engine_bind = self._vectorstore._engine  # pylint: disable=W0212
        #
        with Session(engine_bind) as session:  # pylint: disable=W0212
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
                if "documents" in data_result:
                    data_result["documents"].append(result.document)
                if "metadatas" in data_result:
                    data_result["metadatas"].append(result.cmetadata)
        #
        return data_result

    def _pgvector_delete_by_filter(self, where):
        # Adapted from langchain_community/vectorstores/pgvector.py
        from sqlalchemy.orm import Session  # pylint: disable=C0415,E0401
        #
        try:
            engine_bind = self._vectorstore._bind  # pylint: disable=W0212
        except:  # pylint: disable=W0702
            engine_bind = self._vectorstore._engine  # pylint: disable=W0212
        #
        with Session(engine_bind) as session:  # pylint: disable=W0212
            collection = self._vectorstore.get_collection(session)
            if not collection:
                raise ValueError("Collection not found")
            #
            filter_by = [self._vectorstore.EmbeddingStore.collection_id == collection.uuid]
            if where:
                if self._vectorstore.use_jsonb:
                    filter_clauses = self._vectorstore._create_filter_clause(where)  # pylint: disable=W0212
                    if filter_clauses is not None:
                        filter_by.append(filter_clauses)
                else:
                    # Old way of doing things
                    filter_clauses = self._vectorstore._create_filter_clause_json_deprecated(where)  # pylint: disable=W0212
                    filter_by.extend(filter_clauses)
            #
            _type = self._vectorstore.EmbeddingStore
            #
            results = (
                session.query(self._vectorstore.EmbeddingStore)
                .filter(*filter_by)
                .all()
            )
            #
            for result in results:
                session.delete(result)
            #
            session.commit()
