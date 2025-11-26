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

import importlib
from json import dumps
from traceback import format_exc
from langchain.chains.llm import LLMChain

from langchain_community.llms import __getattr__ as get_llm, __all__ as llms  # pylint: disable=E0401
from langchain_community.chat_models import __all__ as chat_models  # pylint: disable=E0401

from langchain_community.embeddings import __all__ as embeddings  # pylint: disable=E0401

from langchain_community.vectorstores import __all__ as vectorstores  # pylint: disable=E0401
from langchain_community.vectorstores import __getattr__ as get_vectorstore_cls  # pylint: disable=E0401

from langchain.prompts import PromptTemplate  # pylint: disable=E0401

from langchain.schema import HumanMessage, SystemMessage

from ...llms.preloaded import PreloadedEmbeddings, PreloadedChatModel  # pylint: disable=E0401
from ..retrievers.AlitaRetriever import AlitaRetriever
from ..tools.log import print_log



def get_model(model_type: str, model_params: dict):
    """ Get LLM or ChatLLM """
    if model_type is None:
        return None
    if "." in model_type:
        target_pkg, target_name = model_type.rsplit(".", 1)
        target_cls = getattr(
            importlib.import_module(target_pkg),
            target_name
        )
        return target_cls(**model_params)
    if model_type in llms:
        return get_llm(model_type)(**model_params)
    if model_type == "PreloadedChatModel":
        return PreloadedChatModel(**model_params)
    if model_type in chat_models:
        model = getattr(
            __import__("langchain_community.chat_models", fromlist=[model_type]),
            model_type
        )
        return model(**model_params)
    raise RuntimeError(f"Unknown model type: {model_type}")


# TODO: review usage of this function
def get_embeddings(embeddings_model: str, embeddings_params: dict):
    """ Get *Embeddings """
    if embeddings_model is None:
        return None
    if "." in embeddings_model:
        target_pkg, target_name = embeddings_model.rsplit(".", 1)
        target_cls = getattr(
            importlib.import_module(target_pkg),
            target_name
        )
        return target_cls(**embeddings_params)
    if embeddings_model == "PreloadedEmbeddings":
        return PreloadedEmbeddings(**embeddings_params)
    if embeddings_model == "Chroma":
        from langchain_chroma import Chroma
        return Chroma(**embeddings_params)
    if embeddings_model in embeddings:
        model = getattr(
            __import__("langchain_community.embeddings", fromlist=[embeddings_model]),
            embeddings_model
        )
        return model(**embeddings_params)
    raise RuntimeError(f"Unknown Embedding type: {embeddings_model}")


def summarize(llmodel, document, summorization_prompt, metadata_key='document_summary'):
    if llmodel is None:
        return document
    content_length = len(document.page_content)
    # TODO: Magic number need to be removed
    if content_length < 1000 and metadata_key == 'document_summary':
        return document
    file_summary = summorization_prompt
    result = llm_predict(llmodel, file_summary, document.page_content)
    if result:
        document.metadata[metadata_key] = result
    return document


def llm_predict(llmodel, prompt, content):
    file_summary_prompt = PromptTemplate.from_template(prompt, template_format='jinja2')
    llm = LLMChain(
        llm=llmodel,
        prompt=file_summary_prompt,
        verbose=True,
    )
    content_length = len(content)
    print_log(f"Querying content length: {content_length}")
    try:
        result = llm.predict(content=content)
        return result
    except:  # pylint: disable=W0702
        print_log("Failed to generate summary: ", format_exc())
        return ""

def get_vectorstore(vectorstore_type, vectorstore_params, embedding_func=None):
    """ Get vector store obj """
    if vectorstore_type is None:
        return None
    #
    if vectorstore_type == "PGVector" and isinstance(vectorstore_params, dict):
        vectorstore_params = vectorstore_params.copy()
        new_pgvector = False
        #
        conn_str = vectorstore_params.get("connection_string", "")
        if conn_str.startswith("postgresql+psycopg:"):
            vectorstore_params["connection"] = vectorstore_params.pop("connection_string")
            new_pgvector = True
        #
        sdk_options = vectorstore_params.pop("alita_sdk_options", {})
        #
        if "target_schema" in sdk_options and conn_str:
            import sqlalchemy  # pylint: disable=C0415,E0401
            from sqlalchemy.orm import Session  # pylint: disable=C0415,E0401
            from sqlalchemy.schema import CreateSchema  # pylint: disable=E0401,C0415
            #
            engine = sqlalchemy.create_engine(url=conn_str)
            schema_name = sdk_options["target_schema"]
            #
            with Session(engine) as session:  # pylint: disable=W0212
                session.execute(
                    CreateSchema(
                        schema_name,
                        if_not_exists=True,
                    )
                )
                session.commit()
            #
            vectorstore_params["engine_args"] = {
                "execution_options": {
                    "schema_translate_map": {
                        None: schema_name,
                    },
                },
            }
        #
        if new_pgvector:
            if embedding_func:
                vectorstore_params["embeddings"] = embedding_func
            #
            from langchain_postgres import PGVector  # pylint: disable=E0401,C0415
            return PGVector(**vectorstore_params)
    #
    if vectorstore_type in vectorstores:
        vectorstore_params = vectorstore_params.copy()
        #
        if embedding_func:
            vectorstore_params['embedding_function'] = embedding_func
        #
        return get_vectorstore_cls(vectorstore_type)(**vectorstore_params)
    #
    raise RuntimeError(f"Unknown VectorStore type: {vectorstore_type}")

def add_documents(vectorstore, documents, ids = None) -> list[str]:
    """ Add documents to vectorstore """
    if vectorstore is None:
        return None
    texts = []
    metadata = []
    for document in documents:
        if not document.page_content:
            continue
        texts.append(document.page_content)
        for key in document.metadata:
            if isinstance(document.metadata[key], list):
                document.metadata[key] = "; ".join([str(val) for val in document.metadata[key]])
            if isinstance(document.metadata[key], dict):
                document.metadata[key] = dumps(document.metadata[key])
        metadata.append(document.metadata)
    return vectorstore.add_texts(texts, metadatas=metadata, ids=ids)


def generateResponse(
        input, guidance_message, context_message, collection, top_k=5,
        ai_model=None, ai_model_params=None,
        embedding_model=None, embedding_model_params=None,
        vectorstore=None, vectorstore_params=None,
        weights=None,
        stream=False,
    ):
    """ Deprecated """
    embedding = get_embeddings(embedding_model, embedding_model_params)
    vectorstore_params['collection_name'] = collection
    vs = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
    ai = get_model(ai_model, ai_model_params)
    retriever = AlitaRetriever(
        vectorstore=vs,
        doc_library=collection,
        top_k = top_k,
        page_top_k=1,
        weights=weights
    )
    docs = retriever.invoke(input)
    context = f'{guidance_message}\n\n'
    references = set()
    messages = []
    for doc in docs[:top_k]:
        context += f'{doc.page_content}\n\n'
        references.add(doc.metadata["source"])
    messages.append(SystemMessage(content=context_message))
    messages.append(HumanMessage(content=context))
    messages.append(HumanMessage(content=input))
    if stream:
        return {
            "response_iterator": ai.stream(messages),
            "references": references
        }
    response_text = ai.invoke(messages).content

    return {
        "response": response_text,
        "references": references
    }
