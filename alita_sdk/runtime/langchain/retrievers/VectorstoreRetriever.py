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
from typing import Any, Dict, List, Optional
from langchain_core.callbacks.manager import Callbacks
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun


class VectorstoreRetriever(BaseRetriever):
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

    def get_relevant_documents(
        self,
        input: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> List[Document]:
        vs_retriever = self.vectorstore.as_retriever(
            search_kwargs={
                "k": self.top_k,
                "filter": {
                    "library": self.doc_library,
                },
            },
        )
        #
        docs = vs_retriever.get_relevant_documents(input)
        #
        for doc in docs:
            if "data" in doc.metadata:
                doc.page_content = doc.metadata.pop("data")
        #
        return docs
