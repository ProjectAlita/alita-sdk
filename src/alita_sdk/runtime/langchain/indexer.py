# Copyright (c) 2023 Artem Rozumenko
# pylint: disable=C0415
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Indexer entrypoints """

import io
import os
import json
import hashlib
import operator
import tempfile
import threading
import importlib
import concurrent.futures

from typing import Optional

from .tools import log


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
        indexer_extras=None,
):
    #
    log.info("Importing packages")
    #
    from langchain_core.documents import Document
    #
    from .interfaces.llm_processor import (
        get_embeddings,
        get_vectorstore,
        get_model,
        summarize,
        llm_predict,
        add_documents,
    )
    from .interfaces.loaders import loader
    from .interfaces.splitters import Splitter
    #
    from .tools.log import print_log
    from .tools.vector import VectorAdapter
    from .tools.utils import (
        replace_source,
        download_nltk,
        LockedIterator,
    )
    #
    log.info("Checking NLTK")
    #
    try:
        download_nltk("./nltk_data", force=False)
    except Exception as e:
        print_log("Failed to download nltk data", str(e))
    #
    log.info("Starting")
    #
    # Logic is the following:
    # 1. Loader and its params to get data
    # 2. Keyword extractor and its params to get keywords (for the whole file)
    # 3. Splitter and its params to split data (here we may need to use different ar)
    # 4. Keyword extractor and its params to get keywords (for the splitted data)
    # 5. Embedder and its params to get embeddings (for the splitted data)
    #
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    #
    vectoradapter = VectorAdapter(
        vectorstore=vectorstore,
        embeddings=embedding,
        quota_params=quota_params,
    )
    #
    kw_extractor = None
    if kw_for_document and kw_plan:
        if isinstance(indexer_extras, dict) and indexer_extras.get("use_kw_embeddings", False):
            indexer_extras["embeddings"] = embedding
        #
        from .interfaces.kwextractor import KWextractor
        kw_extractor = KWextractor(kw_plan, kw_args, indexer_extras)
    #
    llmodel = get_model(ai_model, ai_model_params)
    #
    vectoradapter.quota_check(
        enforce=False,
        tag="Quota (before pre-cleanup)",
        verbose=True,
    )
    #
    if bins_with_llm and llmodel is not None:
        loader_params['bins_with_llm'] = bins_with_llm
        loader_params['llm'] = llmodel
    #
    # Delete stale 'dataset' documents from vectorstore before (re-)indexing
    vectoradapter.delete_dataset(dataset)
    vectoradapter.persist()
    #
    vectoradapter.vacuum()
    #
    quota_result = vectoradapter.quota_check(
        enforce=True,
        tag="Quota (after pre-cleanup)",
        verbose=True,
    )
    #
    if not quota_result["ok"]:
        return {
            "ok": False,
            "error": "Storage quota exceeded",
        }
    #
    og_keywords_set_for_source = set()
    #
    target_path = None
    target_lock = threading.Lock()
    #
    if chunk_processing_prompt:
        artifact_tmp = tempfile.mkdtemp()
        target_path = os.path.join(artifact_tmp, "Metadataextract.txt")
    #
    use_threads = isinstance(indexer_extras, dict) and indexer_extras.get("use_threads", False)
    #
    if use_threads:
        safe_loader = LockedIterator(loader(loader_name, loader_params, load_params))
        num_threads = indexer_extras.get("num_threads", 10)
    else:
        safe_loader = loader(loader_name, loader_params, load_params)
    #
    def _process_documents():
        for document in safe_loader:
            replace_source(document, source_replacers, keys=["source", "table_source"])
            #
            # Add: two records/placeholders here - summary + keywords
            if document_processing_prompt:
                try:
                    document = summarize(llmodel, document, document_processing_prompt)
                    if document_debug:
                        print_log("Summary: ", document.metadata.get('document_summary', ''))
                except Exception as e:
                    print_log("Failed to generate document summary", str(e))
            #
            if kw_for_document and kw_extractor.extractor:
                if len(document.metadata.get('keywords', [])) == 0 and \
                        len(document.page_content) > 1000:
                    #
                    document.metadata['keywords'] = kw_extractor.extract_keywords(
                        document.metadata.get('document_summary', '') + '\n' + document.page_content
                    )
                    if document_debug:
                        print_log("Keywords: ", document.metadata['keywords'])
            #
            if chunk_processing_prompt:
                try:
                    result = llm_predict(
                        llmodel, chunk_processing_prompt,
                        document.metadata.get('document_summary', '') + '\n' + \
                            document.page_content,
                    )
                    #
                    with target_lock:
                        with open(target_path, "a") as f:
                            f.write(result + "\n")
                except Exception as e:
                    print_log("Failed to generate document metadata", str(e))
            #
            splitter = Splitter(**splitter_params)
            #
            for index, document in enumerate(splitter.split(document, splitter_name)):
                #
                _documents = []
                #
                if document.metadata.get('keywords'):
                    _documents.append(
                        Document(
                            page_content=', '.join(document.metadata['keywords']),
                            metadata={
                                'source': document.metadata['source'],
                                'type': 'keywords',
                                'library': library,
                                'source_type': loader_name,
                                'dataset': dataset,
                            }
                        )
                    )
                #
                if document.metadata.get('document_summary'):
                    _documents.append(
                        Document(
                            page_content=document.metadata['document_summary'],
                            metadata={
                                'source': document.metadata['source'],
                                'type': 'document_summary',
                                'library': library,
                                'source_type': loader_name,
                                'dataset': dataset,
                            }
                        )
                    )
                #
                # og_data is only set by TableLoader
                #
                if document.metadata.get('og_data'):
                    _documents.append(
                        Document(
                            page_content=document.page_content,  # cleansed_data
                            metadata={
                                'source': document.metadata['source'],
                                'type': 'data',
                                'library': library,
                                'source_type': loader_name,
                                'dataset': dataset,
                                'chunk_index': index,
                                'data': document.metadata['og_data'],
                            }
                        )
                    )
                    # Only save columns (=file keywords) once per source
                    if document.metadata['table_source'] not in og_keywords_set_for_source:
                        og_keywords_set_for_source.add(document.metadata['table_source'])
                        _documents.append(
                            Document(
                                page_content=', '.join(document.metadata['columns']),
                                metadata={
                                    'source': document.metadata['table_source'],
                                    'type': 'keywords',
                                    'library': library,
                                    'source_type': loader_name,
                                    'dataset': dataset,
                                }
                            )
                        )
                #
                else:
                    _documents.append(
                        Document(
                            page_content=document.page_content,
                            metadata={
                                'source': document.metadata['source'],
                                'type': 'data',
                                'library': library,
                                'source_type': loader_name,
                                'dataset': dataset,
                                'chunk_index': index,
                            }
                        )
                    )
                #
                if document_debug:
                    print_log(_documents)
                #
                for _document in _documents:
                    if "\x00" in _document.page_content:
                        _document.page_content = _document.page_content.replace("\x00", "")
                #
                if max_docs_per_add is None:
                    add_documents(
                        vectorstore=vectoradapter.vectorstore,
                        documents=_documents,
                    )
                else:
                    for idx in range(0, len(_documents), max_docs_per_add):
                        _docs_add_chunk = _documents[idx:idx+max_docs_per_add]
                        add_documents(
                            vectorstore=vectoradapter.vectorstore,
                            documents=_docs_add_chunk,
                        )
                #
                quota_result = vectoradapter.quota_check(
                    enforce=True,
                    tag="Quota (docs added)",
                    verbose=document_debug,
                )
                #
                if not quota_result["ok"]:
                    return {
                        "ok": False,
                        "error": "Storage quota exceeded",
                    }
            #
            vectoradapter.persist()
            #
            quota_result = vectoradapter.quota_check(
                enforce=True,
                tag="Quota (doc done)",
                verbose=document_debug,
            )
            #
            if not quota_result["ok"]:
                return {
                    "ok": False,
                    "error": "Storage quota exceeded",
                }
        #
        return {"ok": True}
    #
    if use_threads:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_threads)
        futures = []
        #
        log.info("Submitting tasks")
        #
        for _ in range(num_threads):
            futures.append(
                executor.submit(_process_documents)
            )
        #
        log.info("Waiting for tasks")
        #
        for future in concurrent.futures.as_completed(futures):
            try:
                process_result = future.result()
                #
                if not process_result["ok"]:
                    log.info("Got error, shutting down")
                    #
                    executor.shutdown(
                        wait=True,
                        cancel_futures=True,
                    )
                    #
                    return process_result
            except:  # pylint: disable=W0702
                log.info("Got exception, shutting down")
                #
                executor.shutdown(
                    wait=True,
                    cancel_futures=True,
                )
                #
                raise
        #
        log.info("Shutting down")
        #
        executor.shutdown(
            wait=True,
        )
    else:
        process_result = _process_documents()
        #
        if not process_result["ok"]:
            return process_result
    #
    return {"ok": True, "target_path": target_path}


def index(
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
        indexer_extras=None,
):
    return main(
        dataset=dataset,
        library=library,
        loader_name=loader_name,
        loader_params=loader_params,
        load_params=load_params,
        embedding_model=embedding_model,
        embedding_model_params=embedding_model_params,
        kw_plan=kw_plan,
        kw_args=kw_args,
        splitter_name=splitter_name,
        splitter_params=splitter_params,
        document_processing_prompt=document_processing_prompt,
        chunk_processing_prompt=chunk_processing_prompt,
        ai_model=ai_model,
        ai_model_params=ai_model_params,
        vectorstore=vectorstore,
        vectorstore_params=vectorstore_params,
        source_replacers=source_replacers,
        document_debug=document_debug,
        kw_for_document=kw_for_document,
        quota_params=quota_params,
        bins_with_llm=bins_with_llm,
        max_docs_per_add=max_docs_per_add,
        indexer_extras=indexer_extras,
    )


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
    """ Search for documents based on chat history

    Args:
        chat_history (list): List of chat messages [HumanMessage(content="What I want to search for")]
        str_content (bool): Return documents in response
        embedding_model (str): Embedding model name
        embedding_model_params (dict): Embedding model parameters
        vectorstore (str): Vectorstore name
        vectorstore_params (dict): Vectorstore parameters
        collection (str): Collection name
        top_k (int): Number of top documents to return
        weights (dict): Weights for RAG retriever

    Returns:
        str: Documents content
        set: References
    """
    #
    log.info("Importing packages")
    #
    from .interfaces.llm_processor import (
        get_embeddings,
        get_vectorstore,
    )
    #
    from .tools.vector import VectorAdapter
    #
    from .retrievers.AlitaRetriever import AlitaRetriever
    #
    vectorstore_params['collection_name'] = collection
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vs = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    #
    vectoradapter = VectorAdapter(
        vectorstore=vs,
        embeddings=embedding,
    )
    #
    if retriever is None:
        retriever_cls = AlitaRetriever
    else:
        retriever_pkg, retriever_name = retriever.rsplit(".", 1)
        retriever_cls = getattr(
            importlib.import_module(retriever_pkg),
            retriever_name
        )
    #
    log.info("Starting")
    #
    retriever_obj = retriever_cls(
        vectorstore=vectoradapter.vectorstore,
        doc_library=collection,
        top_k=top_k,
        page_top_k=page_top_k,
        fetch_k=fetch_k,
        lower_score_better=lower_score_better,
        document_debug=document_debug,
        weights=weights,
    )
    #
    docs = retriever_obj.invoke(chat_history[-1].content)
    #
    references = set()
    docs_content = ""
    #
    for doc in docs[:top_k]:
        docs_content += f'{doc.page_content}\n\n'
        references.add(doc.metadata["source"])
    #
    if str_content:
        return docs_content, references
    #
    return docs, references


def predict(
        chat_history=[],
        guidance_message=None,
        context_message=None,
        collection=None,
        top_k=5,
        ai_model=None,
        ai_model_params=None,
        embedding_model=None,
        embedding_model_params=None,
        vectorstore=None,
        vectorstore_params=None,
        weights=None,
        page_top_k=1,
        fetch_k=10,
        lower_score_better=True,
        retriever=None,
        document_debug=False,
        stream=False,
        return_monitoring_data=False,
):
    """ Generate prediction based on chat history and results of RAG search

    Args:
        chat_history (list): List of chat messages (Langchain style messages)
        guidance_message (str): Guidance message (Optional message to be added as a divider for search results and context)
        context_message (str): Context message (Optional message to be added as a context of query, exaplaining the structure of message including results of search)
        collection (str): Collection name
        top_k (int): Number of top documents to return
        ai_model (str): AI model name
        ai_model_params (dict): AI model parameters
        embedding_model (str): Embedding model name
        embedding_model_params (dict): Embedding model parameters
        vectorstore (str): Vectorstore name
        vectorstore_params (dict): Vectorstore parameters
        weights (dict): Weights for RAG retriever
        stream (bool): Stream response

    Returns:
        str: Generated response
        set: References to documents
    """
    #
    log.info("Importing packages")
    #
    from langchain.schema import HumanMessage
    #
    from .interfaces.llm_processor import (
        get_model,
    )
    #
    log.info("Starting")
    #
    context, references = search(
        chat_history=chat_history,
        str_content=True,
        embedding_model=embedding_model,
        embedding_model_params=embedding_model_params,
        vectorstore=vectorstore,
        vectorstore_params=vectorstore_params,
        collection=collection,
        top_k=top_k,
        weights=weights,
        page_top_k=page_top_k,
        fetch_k=fetch_k,
        lower_score_better=lower_score_better,
        retriever=retriever,
        document_debug=document_debug,
    )
    #
    messages = []
    #
    if len(chat_history) > 1:
        for message in chat_history[:-1]:
            messages.append(message)
    #
    if context_message:
        messages.append(HumanMessage(content=context_message))
    #
    if guidance_message:
        context = f'{guidance_message}\n\n{context}'
    #
    messages.append(HumanMessage(content=context))
    messages.append(chat_history[-1])
    #
    ai = get_model(ai_model, ai_model_params)
    #
    monitoring_data = {
        "ai": ai,
        "messages": messages,
    }
    #
    if stream:
        result = {
            "response_iterator": ai.stream(messages),
            "references": references,
        }
        #
        if return_monitoring_data:
            result["monitoring_data"] = monitoring_data
        #
        return result
    #
    response = ai.invoke(messages)
    result = {
        "response": response.content,
        "references": references,
    }
    #
    if return_monitoring_data:
        result["monitoring_data"] = monitoring_data
    #
    return result


def deduplicate(
        embedding_model,
        embedding_model_params,
        vectorstore,
        vectorstore_params,
        collection,
        cut_off_score,
        cutoff_func="ge", # or "le" or "gt" or "lt" etc
        score_func="cos_sim",
        search_top=15,
        search_key="sha256",
        preview_top=15,
        exclude_fields=None, # List of strings which should not participate in comparison
        show_additional_metadata=False, # the checkbox which will allow the metadata to be shown in main report
):
    """ Deduplication """
    #
    log.info("Importing packages")
    #
    from langchain_core.documents import Document
    #
    from .interfaces.llm_processor import (
        get_embeddings,
        get_vectorstore,
    )
    #
    from .tools.vector import VectorAdapter
    #
    log.info("Starting")
    #
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    #
    vectoradapter = VectorAdapter(
        vectorstore=vectorstore,
        embeddings=embedding,
    )
    #
    data = vectoradapter.get_data(
        where={"$and": [{"library": collection}, {"type": "data"}]},
        include=["documents", "metadatas"],
    )
    #
    log.debug("Got %d documents from vectoradapter", len(data["documents"]))
    #
    data["embeddings"] = []
    for doc_data in data["documents"]:
        data["embeddings"].append(vectoradapter.embeddings.embed_query(doc_data))
    #
    cutoff = cut_off_score
    cutoff_op = getattr(operator, cutoff_func)
    #
    if exclude_fields is None:
        exclude_fields = []
    #
    excluded_fields_set = set(exclude_fields)
    #
    from .tools.utils import equalize_markdown, equalize_openpyxl
    #
    records = []
    #
    if score_func in ["search", "search_by_vector"]:
        #
        def _same_doc(doc_a, doc_b):
            return doc_a.page_content == doc_b.page_content and \
                doc_a.metadata.get("data", "") == doc_b.metadata.get("data", "") and \
                doc_a.metadata.get("source", "") == doc_b.metadata.get("source", "") and \
                doc_a.metadata.get("chunk_index", "") == doc_b.metadata.get("chunk_index", "")
        #
        def _doc_key(doc):
            if search_key.startswith("col:") and "data" in doc.metadata:
                data = json.loads(doc.metadata["data"])
                return data[search_key.split(":", 1)[1]]
            #
            if search_key.startswith("meta:"):
                return doc.metadata[search_key.split(":", 1)[1]]
            #
            hash_algo = getattr(hashlib, search_key)
            data = "".join([
                str(doc.page_content),
                str(doc.metadata.get("data", "")),
                str(doc.metadata.get("source", "")),
                str(doc.metadata.get("chunk_index", "")),
            ])
            return hash_algo(data.encode()).hexdigest()
        #
        known_pairs = set()
        #
        for idx, doc_data in enumerate(data["documents"]):
            doc_a = Document(
                page_content=doc_data,
                metadata=data["metadatas"][idx],
            )
            #
            doc_a_data = doc_a.page_content
            if "data" in doc_a.metadata:
                doc_a_data = json.loads(doc_a.metadata["data"])
            #
            doc_a_metadata = doc_a.metadata.copy()
            doc_a_metadata.pop("data", None)
            #
            doc_a_key = _doc_key(doc_a)
            #
            if score_func == "search":
                items = vectorstore.similarity_search_with_score(
                    doc_data,
                    k=search_top,
                )
            else:
                items = vectorstore.similarity_search_by_vector_with_relevance_scores(
                    data["embeddings"][idx],
                    k=search_top,
                )
            #
            for doc_b, score in items:
                if cutoff_op(score, cutoff):
                    if _same_doc(doc_a, doc_b):
                        continue
                    #
                    doc_b_key = _doc_key(doc_b)
                    #
                    pair_v1 = ":".join([doc_a_key, doc_b_key])
                    pair_v2 = ":".join([doc_b_key, doc_a_key])
                    #
                    if pair_v1 in known_pairs or pair_v2 in known_pairs:
                        continue
                    #
                    known_pairs.add(pair_v1)
                    #
                    # Add record:
                    # - pairs: for preview
                    # - row: for xlsx
                    #
                    record = {
                        "score": round(score, 3),
                        "pairs": {},
                        "row": {},
                    }
                    #
                    doc_b_data = doc_b.page_content
                    if "data" in doc_b.metadata:
                        doc_b_data = json.loads(doc_b.metadata["data"])
                    #
                    doc_b_metadata = doc_b.metadata.copy()
                    doc_b_metadata.pop("data", None)
                    #
                    if isinstance(doc_a_data, str):
                        col1, col2 = equalize_markdown(
                            doc_a_data,
                            doc_b_data
                        )
                        #
                        record["pairs"]["Document Content #1"] = col1
                        record["pairs"]["Document Content #2"] = col2
                        #
                        xcol1, xcol2 = equalize_openpyxl(
                            doc_a_data,
                            doc_b_data
                        )
                        #
                        record["row"]["Document Content #1"] = xcol1
                        record["row"]["Document Content #2"] = xcol2
                    else:
                        for col in doc_a_data.keys():
                            # For the columns excluded from comparizon don't do the difference analysis since they are used only for grouping the results
                            if col in excluded_fields_set:
                                col1, col2 = doc_a_data[col], doc_b_data[col]
                                xcol1, xcol2 = doc_a_data[col], doc_b_data[col]
                            else:
                                col1, col2 = equalize_markdown(
                                    doc_a_data[col],
                                    doc_b_data[col]
                                )
                                xcol1, xcol2 = equalize_openpyxl(
                                    doc_a_data[col],
                                    doc_b_data[col]
                                )
                            # Set the columns content for markdown output
                            record["pairs"][f'{col} #1'] = col1
                            record["pairs"][f'{col} #2'] = col2
                            # Set the columns content for Excel output
                            record["row"][f'{col} #1'] = xcol1
                            record["row"][f'{col} #2'] = xcol2
                        # Show the service data in the deduplication report
                        # Show service data only if special checkbox is switched on
                        if show_additional_metadata:
                            for col in doc_a_metadata.keys():
                                record["pairs"][f'{col} #1'] = doc_a_metadata[col]
                                record["pairs"][f'{col} #2'] = doc_b_metadata[col]
                                #
                                record["row"][f'{col} #1'] = doc_a_metadata[col]
                                record["row"][f'{col} #2'] = doc_b_metadata[col]
                    # Append the result record to the records which will be shown in the deduplication report
                    records.append(record)
    else:
        embeddins_lib = {
            "embeddings": data["embeddings"],
            "sentences": [],
            "metadata": data["metadatas"],
        }
        #
        for idx, meta in enumerate(embeddins_lib["metadata"]):
            if "data" in meta:
                embeddins_lib["sentences"].append(json.loads(meta.pop("data")))
            else:
                embeddins_lib["sentences"].append(data["documents"][idx])
        #
        from sentence_transformers import util
        #
        if score_func == "cdist":
            import torch
            score_op = torch.cdist
            score_arg = torch.Tensor(embeddins_lib["embeddings"])
        elif score_func in ["cos_sim", "dot_score"]:
            score_op = getattr(util, score_func)
            score_arg = embeddins_lib["embeddings"]
        elif score_func in ["l2", "cosine", "ip"]:
            import numpy
            from chromadb.utils import distance_functions
            score_op_func = getattr(distance_functions, score_func)
            def score_op(a, b):
                class _outer:
                    def __getitem__(self, outer_key):
                        class _inner:
                            def __getitem__(self, inner_key):
                                return score_op_func(
                                    numpy.array(a[outer_key]),
                                    numpy.array(b[inner_key])
                                )
                        return _inner()
                return _outer()
            score_arg = embeddins_lib["embeddings"]
        else:
            raise ValueError(f"Unknown score function: {score_func}")
        #
        # Ported and updated 'legacy' code below
        #
        cosine_scores = score_op(score_arg, score_arg)
        score_dim = len(embeddins_lib["embeddings"])
        #
        for iindex in range(score_dim):
            for jindex in range(score_dim):
                score = cosine_scores[iindex][jindex]
                #
                if cutoff_op(score, cutoff) and iindex < jindex:
                    #
                    # Add record:
                    # - pairs: for preview
                    # - row: for xlsx
                    #
                    record = {
                        "score": round(score.item(), 3),
                        "pairs": {},
                        "row": {},
                    }
                    #
                    if isinstance(embeddins_lib["sentences"][iindex], str):
                        col1, col2 = equalize_markdown(
                            embeddins_lib["sentences"][iindex],
                            embeddins_lib["sentences"][jindex]
                        )
                        #
                        record["pairs"]["Document Content #1"] = col1
                        record["pairs"]["Document Content #2"] = col2
                        #
                        xcol1, xcol2 = equalize_openpyxl(
                            embeddins_lib["sentences"][iindex],
                            embeddins_lib["sentences"][jindex]
                        )
                        #
                        record["row"]["Document Content #1"] = xcol1
                        record["row"]["Document Content #2"] = xcol2
                    else:
                        for col in embeddins_lib["sentences"][0].keys():
                            # For the columns excluded from comparizon don't do the difference analysis since they are used only for grouping the results
                            if col in excluded_fields_set:
                                col1, col2 = (embeddins_lib["sentences"][iindex][col],
                                              embeddins_lib["sentences"][jindex][col])
                                xcol1, xcol2 = (embeddins_lib["sentences"][iindex][col],
                                                embeddins_lib["sentences"][jindex][col])
                            else:
                                col1, col2 = equalize_markdown(
                                    embeddins_lib["sentences"][iindex][col],
                                    embeddins_lib["sentences"][jindex][col]
                                )
                                xcol1, xcol2 = equalize_openpyxl(
                                    embeddins_lib["sentences"][iindex][col],
                                    embeddins_lib["sentences"][jindex][col]
                                )
                            # Set the columns content for markdown output
                            record["pairs"][f'{col} #1'] = col1
                            record["pairs"][f'{col} #2'] = col2
                            # Set the columns content for Excel output
                            record["row"][f'{col} #1'] = xcol1
                            record["row"][f'{col} #2'] = xcol2
                        # Show the service data in the deduplication report
                        # Show service data only if special checkbox is switched on
                        if show_additional_metadata:
                            for col in embeddins_lib["metadata"][0].keys():
                                record["pairs"][f'{col} #1'] = embeddins_lib["metadata"][iindex][col]
                                record["pairs"][f'{col} #2'] = embeddins_lib["metadata"][jindex][col]
                                #
                                record["row"][f'{col} #1'] = embeddins_lib["metadata"][iindex][col]
                                record["row"][f'{col} #2'] = embeddins_lib["metadata"][jindex][col]
                    # Append the result record to the records which will be shown in the deduplication report
                    records.append(record)
    #
    # Sort by score
    #
    records.sort(key=lambda x: x["score"], reverse=cutoff_func.startswith("g"))
    #
    # Preview pairs
    #
    pairs = [{"score": record["score"], **record["pairs"]} for record in records[:preview_top]]
    #
    # File XLSX
    #
    rows = [{"score": record["score"], **record["row"]} for record in records]
    file_obj = io.BytesIO()
    #
    from openpyxl import Workbook
    #
    wb = Workbook()
    ws = wb.active
    #
    if rows:
        ws.append(list(rows[0].keys()))
        for row in rows:
            ws.append(list(row.values()))
    #
    wb.save(file_obj)
    xlsx_data = file_obj.getvalue()
    #
    # Done
    #
    return pairs, xlsx_data


def delete(
        embedding_model: str,
        embedding_model_params: dict,
        vectorstore: Optional[str] = None,
        vectorstore_params: Optional[dict] = {},
        dataset: str = None,
        library: str = None,
        quota_params=None,
):
    """ Delete dataset documents from vectorstore """
    #
    log.info("Importing packages")
    #
    from .interfaces.llm_processor import (
        get_embeddings,
        get_vectorstore,
    )
    #
    from .tools.vector import VectorAdapter
    #
    log.info("Starting")
    #
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vectorstore = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    #
    vectoradapter = VectorAdapter(
        vectorstore=vectorstore,
        embeddings=embedding,
        quota_params=quota_params,
    )
    #
    vectoradapter.quota_check(
        enforce=False,
        tag=f"Quota (before deletion of ds={dataset}, lib={library})",
        verbose=True,
    )
    #
    if dataset is not None:
        vectoradapter.delete_dataset(dataset)
        vectoradapter.persist()
    #
    if library is not None:
        vectoradapter.delete_library(library)
        vectoradapter.persist()
    #
    vectoradapter.vacuum()
    #
    vectoradapter.quota_check(
        enforce=False,
        tag=f"Quota (after deletion of ds={dataset}, lib={library})",
        verbose=True,
    )
