from langchain_core.documents import Document

from alita_sdk.runtime.utils.utils import IndexerKeywords
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit


class NonCodeIndexerToolkit(BaseIndexerToolkit):
    def _get_indexed_data(self, collection_suffix: str):
        return self.vector_adapter.get_indexed_data(self, collection_suffix)

    def key_fn(self, document: Document):
        return document.metadata.get('id')

    def compare_fn(self, document: Document, idx_data):
        return (document.metadata.get('updated_on')
                and idx_data['metadata'].get('updated_on')
                and document.metadata.get('updated_on') == idx_data['metadata'].get('updated_on'))

    def remove_ids_fn(self, idx_data, key: str):
        return (idx_data[key]['all_chunks'] +
                [idx_data[dep_id]['id'] for dep_id in idx_data[key][IndexerKeywords.DEPENDENT_DOCS.value]] +
                [chunk_db_id for dep_id in idx_data[key][IndexerKeywords.DEPENDENT_DOCS.value] for chunk_db_id in
                 idx_data[dep_id]['all_chunks']])
