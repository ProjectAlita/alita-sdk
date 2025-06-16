# Copyright (c) 2023 Artem Rozumenko
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

from langchain_core.retrievers import BaseRetriever
from typing import Any, Dict, List
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from ..tools.log import print_log
from ..document_loaders.utils import cleanse_data


class AlitaRetriever(BaseRetriever):
    vectorstore: Any  # Instance of vectorstore
    doc_library: str  # Name of the document library
    top_k: int  # Number of documents to return
    page_top_k: int = 1
    weights: Dict[str, float] = {
        'keywords': 0.2,
        'document_summary': 0.5,
        'data': 0.3,
    }
    fetch_k: int = 10
    lower_score_better: bool = True
    document_debug: bool = False
    no_cleanse: bool = False

    class Config:
        arbitrary_types_allowed = True

    def _rerank_documents(self, documents: List[tuple]):
        """ Rerank documents """
        _documents = []
        #
        for (document, score) in documents:
            item = {
                "page_content": document.page_content,
                "metadata": document.metadata,
                "score": score * self.weights.get(document.metadata['type'], 1.0),
            }
            #
            if "data" in item["metadata"]:
                item["page_content"] = item["metadata"].pop("data")
            #
            _documents.append(item)
        #
        return sorted(
            _documents,
            key=lambda x: x["score"],
            reverse=not self.lower_score_better,
        )

    def merge_results(self, input:str, docs: List[dict]):
        results = {}
        #
        for doc in docs:
            if doc['metadata']['source'] not in results.keys():
                results[doc['metadata']['source']] = {
                    'page_content': [],
                    'metadata': {
                        'source' : doc['metadata']['source'],
                    },
                }
                #
                documents = self.vectorstore.similarity_search_with_score(
                    input,
                    filter={'source': doc["metadata"]['source']},
                    k=self.fetch_k,
                )
                #
                for (d, score) in documents:
                    if d.metadata['type'] == 'data':
                        if "data" in d.metadata:
                            results[doc['metadata']['source']]['page_content'].append({
                                "content": d.metadata['data'],
                                "index": d.metadata['chunk_index'],
                                "score": score,
                            })
                        else:
                            results[doc['metadata']['source']]['page_content'].append({
                                "content": d.page_content,
                                "index": d.metadata['chunk_index'],
                                "score": score,
                            })
                    elif d.metadata['type'] == 'document_summary':
                        results[doc['metadata']['source']]['page_content'].append({
                            "content": d.page_content,
                            "index": -1,
                            "score": score,
                        })
                #
                if not results[doc['metadata']['source']]['page_content']:
                    results.pop(doc['metadata']['source'])
            #
            if len(results.keys()) >= self.top_k:
                break
        #
        if self.document_debug:
            print_log("results =", results)
        #
        _docs = []
        #
        for value in results.values():
            _chunks = sorted(
                value['page_content'],
                key=lambda x: x["score"],
                reverse=not self.lower_score_better,
            )
            #
            pages = list(map(lambda x: x['content'], _chunks))
            top_pages = pages[:self.page_top_k]
            #
            if not top_pages:
                continue
            #
            _docs.append(Document(
                page_content="\n\n".join(top_pages),
                metadata=value['metadata'],
            ))
        #
        return _docs

    def get_relevant_documents(
        self,
        input: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> List[Document]:
        #
        # detect if cleanse_data on input is needed
        #
        if not self.no_cleanse:
            test_docs = self.vectorstore.similarity_search_with_score(
                input,
                filter={"$and": [{"library": self.doc_library}, {"type": "data"}]},
                k=1,
            )
            #
            if test_docs and "data" in test_docs[0][0].metadata:
                input = cleanse_data(input)
        #
        if self.document_debug:
            print_log("using input =", input)
        #
        # process
        #
        docs = self.vectorstore.similarity_search_with_score(
            input,
            filter={'library': self.doc_library},
            k=self.fetch_k,
        )
        #
        if self.document_debug:
            print_log("similarity_search =", docs)
        #
        docs = self._rerank_documents(docs)
        #
        if self.document_debug:
            print_log("rerank_documents =", docs)
        #
        docs = self.merge_results(input, docs)
        #
        if self.document_debug:
            print_log("merge_results =", docs)
        #
        return docs
