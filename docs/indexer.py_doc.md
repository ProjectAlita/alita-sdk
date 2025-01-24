# indexer.py

**Path:** `src/alita_sdk/langchain/indexer.py`

## Data Flow

The data flow within `indexer.py` is structured to handle the loading, processing, and indexing of documents. The process begins with the `main` function, which orchestrates the entire workflow. Data is initially loaded using a specified loader, which retrieves documents based on the provided parameters. These documents are then processed to extract keywords and summaries, split into chunks, and finally embedded and stored in a vector store for efficient retrieval.

The data flow can be summarized as follows:
1. **Loading Data:** The loader retrieves documents based on the specified parameters.
2. **Keyword Extraction:** Keywords are extracted from the entire document and from individual chunks if specified.
3. **Splitting Data:** Documents are split into smaller chunks for more granular processing.
4. **Embedding Data:** Chunks are embedded using a specified embedding model.
5. **Storing Data:** Embedded chunks are stored in a vector store for efficient retrieval.

Example:
```python
for document in loader(loader_name, loader_params, load_params):
    replace_source(document, source_replacers, keys=["source", "table_source"])
    if document_processing_prompt:
        document = summarize(llmodel, document, document_processing_prompt)
    if kw_for_document and kw_extractor.extractor:
        document.metadata['keywords'] = kw_extractor.extract_keywords(document.metadata.get('document_summary', '') + '\n' + document.page_content)
    splitter = Splitter(**splitter_params)
    for index, document in enumerate(splitter.split(document, splitter_name)):
        _documents.append(Document(page_content=document.page_content, metadata={...}))
```

## Functions Descriptions

### `main`
The `main` function is the core of the indexing process. It takes various parameters related to data loading, processing, and embedding. It initializes the necessary components, such as the loader, keyword extractor, splitter, and embedding model. The function then orchestrates the loading, processing, and storing of documents.

**Parameters:**
- `dataset`: The name of the dataset.
- `library`: The library to use.
- `loader_name`: The name of the loader to use.
- `loader_params`: Parameters for the loader.
- `load_params`: Additional parameters for loading.
- `embedding_model`: The embedding model to use.
- `embedding_model_params`: Parameters for the embedding model.
- `kw_plan`: Keyword extraction plan.
- `kw_args`: Arguments for keyword extraction.
- `splitter_name`: The name of the splitter to use.
- `splitter_params`: Parameters for the splitter.
- `document_processing_prompt`: Prompt for document processing.
- `chunk_processing_prompt`: Prompt for chunk processing.
- `ai_model`: The AI model to use.
- `ai_model_params`: Parameters for the AI model.
- `vectorstore`: The vector store to use.
- `vectorstore_params`: Parameters for the vector store.
- `source_replacers`: Source replacers for documents.
- `document_debug`: Debug flag for document processing.
- `kw_for_document`: Flag to enable keyword extraction for documents.
- `quota_params`: Parameters for quota management.
- `bins_with_llm`: Flag to enable bins with LLM.
- `max_docs_per_add`: Maximum documents per add operation.

**Returns:**
- A dictionary with the status of the operation and the target path if applicable.

### `index`
The `index` function is a wrapper around the `main` function, providing a simplified interface for indexing documents.

**Parameters:**
- Same as the `main` function.

**Returns:**
- The result of the `main` function.

### `search`
The `search` function performs a search for documents based on the chat history. It uses the specified embedding model and vector store to retrieve relevant documents.

**Parameters:**
- `chat_history`: List of chat messages.
- `str_content`: Flag to return documents as strings.
- `embedding_model`: The embedding model to use.
- `embedding_model_params`: Parameters for the embedding model.
- `vectorstore`: The vector store to use.
- `vectorstore_params`: Parameters for the vector store.
- `collection`: The collection to search in.
- `top_k`: Number of top documents to return.
- `weights`: Weights for the retriever.
- `page_top_k`: Number of top pages to return.
- `fetch_k`: Number of documents to fetch.
- `lower_score_better`: Flag to indicate if lower scores are better.
- `retriever`: The retriever to use.
- `document_debug`: Debug flag for document processing.

**Returns:**
- The content of the documents and their references.

### `predict`
The `predict` function generates a prediction based on the chat history and search results. It uses the specified AI model to generate a response.

**Parameters:**
- Same as the `search` function, with additional parameters for guidance and context messages.

**Returns:**
- The generated response and references to documents.

### `deduplicate`
The `deduplicate` function performs deduplication of documents based on the specified parameters. It uses the embedding model and vector store to identify and remove duplicate documents.

**Parameters:**
- `embedding_model`: The embedding model to use.
- `embedding_model_params`: Parameters for the embedding model.
- `vectorstore`: The vector store to use.
- `vectorstore_params`: Parameters for the vector store.
- `collection`: The collection to deduplicate.
- `cut_off_score`: The cutoff score for deduplication.
- `cutoff_func`: The function to use for cutoff comparison.
- `score_func`: The function to use for scoring.
- `search_top`: Number of top documents to search.
- `search_key`: The key to use for searching.
- `preview_top`: Number of top documents to preview.
- `exclude_fields`: Fields to exclude from comparison.
- `show_additional_metadata`: Flag to show additional metadata.

**Returns:**
- The deduplication results and the XLSX data.

### `delete`
The `delete` function deletes documents from the vector store based on the specified parameters.

**Parameters:**
- `embedding_model`: The embedding model to use.
- `embedding_model_params`: Parameters for the embedding model.
- `vectorstore`: The vector store to use.
- `vectorstore_params`: Parameters for the vector store.
- `dataset`: The dataset to delete.
- `library`: The library to delete.
- `quota_params`: Parameters for quota management.

**Returns:**
- None.

## Dependencies Used and Their Descriptions

### `io`
Used for handling input and output operations, particularly for creating in-memory file objects.

### `os`
Provides a way of using operating system-dependent functionality like reading or writing to the file system.

### `json`
Used for parsing JSON data.

### `hashlib`
Provides a common interface to many secure hash and message digest algorithms.

### `operator`
Exports a set of efficient functions corresponding to the intrinsic operators of Python.

### `importlib`
Provides a way to import modules in runtime.

### `tempfile`
Generates temporary files and directories.

### `langchain_core.documents`
Provides the `Document` class used for handling document data.

### `langchain.schema`
Provides the `HumanMessage` class used for handling chat messages.

### `interfaces.loaders`
Provides the `loader` function for loading documents.

### `interfaces.kwextractor`
Provides the `KWextractor` class for extracting keywords.

### `interfaces.splitters`
Provides the `Splitter` class for splitting documents.

### `interfaces.llm_processor`
Provides various functions for processing documents with language models, such as `get_embeddings`, `summarize`, `get_model`, `get_vectorstore`, `add_documents`, `generateResponse`, and `llm_predict`.

### `tools.utils`
Provides utility functions like `unpack_json`, `download_nltk`, and `replace_source`.

### `tools.vector`
Provides the `VectorAdapter` class for handling vector stores.

### `tools.log`
Provides logging functions like `print_log`.

### `retrievers.AlitaRetriever`
Provides the `AlitaRetriever` class for retrieving documents from the vector store.

## Functional Flow

The functional flow of `indexer.py` is designed to handle the end-to-end process of loading, processing, and indexing documents. The main entry point is the `main` function, which initializes the necessary components and orchestrates the workflow. The `index` function serves as a wrapper around `main`, providing a simplified interface for indexing. The `search` function handles document retrieval based on chat history, while the `predict` function generates responses using an AI model. The `deduplicate` function identifies and removes duplicate documents, and the `delete` function removes documents from the vector store.

Example:
```python
def main(
        dataset: str,
        library:str,
        loader_name: str,
        loader_params: dict,
        load_params: Optional[dict],
        embedding_model: str,
        embedding_model_params: dict,
        kw_plan: Optional[str],
        kw_args: Optional[dict],
        splitter_name: Optional[str] = 'chunks',
        splitter_params: Optional[dict] = {},
        document_processing_prompt: Optional[str] = None,
        chunk_processing_prompt: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_model_params: Optional[dict] = {},
        vectorstore: Optional[str] = None,
        vectorstore_params: Optional[dict] = {},
        source_replacers: Optional[dict] = {},
        document_debug=False,
        kw_for_document=True,
        quota_params=None,
        bins_with_llm = False,
        max_docs_per_add=None,
):
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    vectoradapter = VectorAdapter(vectorstore=vectorstore, embeddings=embedding, quota_params=quota_params)
    kw_extractor = None
    if kw_for_document and kw_plan:
        kw_extractor = KWextractor(kw_plan, kw_args)
    llmodel = get_model(ai_model, ai_model_params)
    vectoradapter.quota_check(enforce=False, tag="Quota (before pre-cleanup)", verbose=True)
    if bins_with_llm and llmodel is not None:
        loader_params['bins_with_llm'] = bins_with_llm
        loader_params['llm'] = llmodel
    vectoradapter.delete_dataset(dataset)
    vectoradapter.persist()
    vectoradapter.vacuum()
    quota_result = vectoradapter.quota_check(enforce=True, tag="Quota (after pre-cleanup)", verbose=True)
    if not quota_result["ok"]:
        return {"ok": False, "error": "Storage quota exceeded"}
    og_keywords_set_for_source = set()
    target_path = None
    if chunk_processing_prompt:
        artifact_tmp = tempfile.mkdtemp()
        target_path = os.path.join(artifact_tmp, "Metadataextract.txt")
    for document in loader(loader_name, loader_params, load_params):
        replace_source(document, source_replacers, keys=["source", "table_source"])
        if document_processing_prompt:
            document = summarize(llmodel, document, document_processing_prompt)
        if kw_for_document and kw_extractor.extractor:
            document.metadata['keywords'] = kw_extractor.extract_keywords(document.metadata.get('document_summary', '') + '\n' + document.page_content)
        if chunk_processing_prompt:
            result = llm_predict(llmodel, chunk_processing_prompt, document.metadata.get('document_summary', '') + '\n' + document.page_content)
            with open(target_path, "a") as f:
                f.write(result + "\n")
        splitter = Splitter(**splitter_params)
        for index, document in enumerate(splitter.split(document, splitter_name)):
            _documents = []
            if document.metadata.get('keywords'):
                _documents.append(Document(page_content=', '.join(document.metadata['keywords']), metadata={...}))
            if document.metadata.get('document_summary'):
                _documents.append(Document(page_content=document.metadata['document_summary'], metadata={...}))
            if document.metadata.get('og_data'):
                _documents.append(Document(page_content=document.page_content, metadata={...}))
                if document.metadata['table_source'] not in og_keywords_set_for_source:
                    og_keywords_set_for_source.add(document.metadata['table_source'])
                    _documents.append(Document(page_content=', '.join(document.metadata['columns']), metadata={...}))
            else:
                _documents.append(Document(page_content=document.page_content, metadata={...}))
            if document_debug:
                print_log(_documents)
            for _document in _documents:
                if "\x00" in _document.page_content:
                    _document.page_content = _document.page_content.replace("\x00", "")
            if max_docs_per_add is None:
                add_documents(vectorstore=vectoradapter.vectorstore, documents=_documents)
            else:
                for idx in range(0, len(_documents), max_docs_per_add):
                    _docs_add_chunk = _documents[idx:idx+max_docs_per_add]
                    add_documents(vectorstore=vectoradapter.vectorstore, documents=_docs_add_chunk)
            quota_result = vectoradapter.quota_check(enforce=True, tag="Quota (docs added)", verbose=document_debug)
            if not quota_result["ok"]:
                return {"ok": False, "error": "Storage quota exceeded"}
        vectoradapter.persist()
        quota_result = vectoradapter.quota_check(enforce=True, tag="Quota (doc done)", verbose=document_debug)
        if not quota_result["ok"]:
            return {"ok": False, "error": "Storage quota exceeded"}
    return {"ok": True, "target_path": target_path}
```

## Endpoints Used/Created

### `search`
The `search` function uses the `AlitaRetriever` class to perform a search for documents based on the chat history. It retrieves relevant documents from the vector store and returns their content and references.

**Example:**
```python
def search(
        chat_history=[],
        str_content=True,
        embedding_model=None,
        embedding_model_params=None,
        vectorstore=None,
        vectorstore_params=None,
        collection=None,
        top_k=5,
        weights=None,
        page_top_k=1,
        fetch_k=10,
        lower_score_better=True,
        retriever=None,
        document_debug=False,
):
    vectorstore_params['collection_name'] = collection
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vs = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    vectoradapter = VectorAdapter(vectorstore=vs, embeddings=embedding)
    if retriever is None:
        retriever_cls = AlitaRetriever
    else:
        retriever_pkg, retriever_name = retriever.rsplit(".", 1)
        retriever_cls = getattr(importlib.import_module(retriever_pkg), retriever_name)
    retriever_obj = retriever_cls(vectorstore=vectoradapter.vectorstore, doc_library=collection, top_k=top_k, page_top_k=page_top_k, fetch_k=fetch_k, lower_score_better=lower_score_better, document_debug=document_debug, weights=weights)
    docs = retriever_obj.invoke(chat_history[-1].content)
    references = set()
    docs_content = ""
    for doc in docs[:top_k]:
        docs_content += f'{doc.page_content}\n\n'
        references.add(doc.metadata["source"])
    if str_content:
        return docs_content, references
    return docs, references
```
