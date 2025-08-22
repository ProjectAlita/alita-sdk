import json
import logging
from typing import Generator
from langchain_text_splitters import RecursiveJsonSplitter
from langchain_core.documents import Document

def json_chunker(file_content_generator: Generator[Document, None, None], config: dict, *args, **kwargs) -> Generator[Document, None, None]:
    max_tokens = config.get("max_tokens", 512)
    for doc in file_content_generator:
        try:
            data_dict = json.loads(doc.page_content)
            chunks = RecursiveJsonSplitter(max_chunk_size=max_tokens).split_json(json_data=data_dict, convert_lists=True)
            if len(chunks) == 1:
                yield doc
                continue
            chunk_id = 1
            for chunk in chunks:
                metadata = doc.metadata.copy()
                metadata['chunk_id'] = chunk_id
                chunk_id += 1
                yield Document(page_content=json.dumps(chunk), metadata=metadata)
        except Exception as e:
            logging.error(f"Failed to chunk document: {e}")
            yield doc