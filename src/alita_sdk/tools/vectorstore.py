from json import dumps
from typing import Any, Optional
from pydantic import BaseModel, model_validator, Field, PrivateAttr
from langchain_core.tools import ToolException
from ..langchain.tools.vector import VectorAdapter
from langchain_core.messages import HumanMessage
from logging import getLogger

logger = getLogger(__name__)

class IndexDocumentsModel(BaseModel):
    documents: Any = Field(description="Generator of documents to index")

class SearchDocumentsModel(BaseModel):
    query: str = Field(description="Search query")
    doctype: str = Field(description="Document type")
    filter: Optional[dict] = Field(description='Filter for metadata of documents, Should be empty string if no filter required. In case needed i.e. " + \
                        "({"id": {"$in": [1, 5, 2, 9]}, {"$and": [{"id": {"$in": [1, 5, 2, 9]}}, " + \
                            "{"location": {"$in": ["pond", "market"]}}]}', default=None)
    search_top: Optional[int] = Field(description="Number of search results", default=10)
    cut_off: Optional[float] = Field(description="Cut off value for search results", default=0.5)
    
class StepBackSearchDocumentsModel(BaseModel):
    query: str = Field(description="Search query")
    doctype: str = Field(description="Document type")
    messages: Optional[list] = Field(description="Conversation history", default=[])
    filter: Optional[dict] = Field(description='Filter for metadata of documents, Should be empty string if no filter required. In case needed i.e. " + \
                        "({"id": {"$in": [1, 5, 2, 9]}, {"$and": [{"id": {"$in": [1, 5, 2, 9]}}, " + \
                            "{"location": {"$in": ["pond", "market"]}}]}', default=None)
    search_top: Optional[int] = Field(description="Number of search results", default=10)
    cut_off: Optional[float] = Field(description="Cut off value for search results", default=0.5)

STEPBACK_PROMPT = """Your task is to convert provided question into a more generic question that will be used for similarity search.
Remove all not important words, question words, but save all names, dates and acronym as in original question.

<input>
{input} 
</input>

Output:
"""

GET_ANSWER_PROMPT = """<search_results>
{search_results}
</search_results>

<conversation_history>
{messages}
</conversation_history>

Please answer the question based on provided search results.
Provided information is already processed and available in the context as list of possibly relevant pieces of the documents.
Use only provided information. Do not make up answer.
If you have no answer and you can not derive it from the context, please provide "I have no answer".
<question>
{input}
</question>
## Answer
Add <ANSWER> here

## Score
Score the answer from 0 to 100, where 0 is not relevant and 100 is very relevant.

## Citations
- source (score)
- source (score)
Make sure to provide unique source for each citation.

## Explanation
How did you come up with the answer?"""

class VectorStoreWrapper(BaseModel):
    llm: Any
    embedding_model: str
    embedding_model_params: dict
    vectorstore_type: str
    vectorstore_params: dict
    max_docs_per_add: int = 100
    _dataset: str = PrivateAttr()
    _embedding: Any = PrivateAttr()
    _vectorstore: Any = PrivateAttr()
    _vectoradapter: Any = PrivateAttr()
    
    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        from ..langchain.interfaces.llm_processor import get_embeddings,get_vectorstore
        logger.debug(f"Validating toolkit: {values}")
        if not values.get('vectorstore_type'):
            raise ValueError("Vectorstore type is required.")
        if not values.get('embedding_model'):
            raise ValueError("Embedding model is required.")
        if not values.get('vectorstore_params'):
            raise ValueError("Vectorstore parameters are required.")
        if not values.get('embedding_model_params'):
            raise ValueError("Embedding model parameters are required.")
        cls._dataset = values.get('vectorstore_params').get('collection_name')
        if not cls._dataset:
            raise ValueError("Collection name is required.")
        cls._embedding = get_embeddings(values['embedding_model'], values['embedding_model_params'])
        cls._vectorstore = get_vectorstore(values['vectorstore_type'], values['vectorstore_params'], embedding_func=cls._embedding)
        cls._vectoradapter = VectorAdapter(
            vectorstore=cls._vectorstore,
            embeddings=cls._embedding,
            quota_params=None,
        )
        return values

    def index_documents(self, documents):
        from ..langchain.interfaces.llm_processor import add_documents
        logger.debug(f"Indexing documents: {documents}")
        self._vectoradapter.delete_dataset(self._dataset)
        self._vectoradapter.persist()
        logger.debug(f"Deleted Dataset")
        #
        self._vectoradapter.vacuum()
        #
        documents_count = 0
        _documents = []
        for document in documents:
            documents_count += 1
            # logger.debug(f"Indexing document: {document}")
            try:
                _documents.append(document)
                if len(_documents) >= self.max_docs_per_add:
                    add_documents(vectorstore=self._vectoradapter.vectorstore, documents=_documents)
                    self._vectoradapter.persist()
                    _documents = []
            except Exception as e:
                from traceback import format_exc
                logger.error(f"Error: {format_exc()}")
                return {"status": "error", "message": f"Error: {format_exc()}"}
        if _documents:
            add_documents(vectorstore=self._vectoradapter.vectorstore, documents=_documents)
            self._vectoradapter.persist()
        return {"status": "ok", "message": f"successfully indexed {documents_count} documents"}


    def search_documents(self, query:str, doctype: str = 'code', filter:dict={}, cut_off: float=0.5, search_top:int=10):
        from alita_tools.code.loaders.codesearcher import search_format as code_format
        if not filter:
            filter = None
        items = self._vectoradapter.vectorstore.similarity_search_with_score(query, filter=filter, k=search_top)
        filtered = []
        if cut_off:
            filtered = [item for item in items if abs(item[1]) >= cut_off]
            items = filtered
        if doctype == 'code':
            return code_format(items)
        else:
            response = []
            for item in items:
                logger.debug(item)
                response.append({
                    'page_content': item[0].page_content, 
                    'metadata': item[0].metadata,
                    'score': item[1]
                })
            return dumps(response, indent=2)
    
    
    def stepback_search(self, query:str, messages: list, doctype: str = 'code', filter:dict={}, cut_off: float=0.5, search_top:int=10):
        result = self.llm.invoke([
            HumanMessage(
                content=[
                    {"type": "text", "text": STEPBACK_PROMPT.format(input=query, messages=messages)},
                ]
            )
        ])
        search_results = self.search_documents(result.content, doctype, filter, cut_off, search_top)
        return dumps(search_results, indent=2)

    def stepback_summary(self, query:str, messages: list, doctype: str = 'code', filter:dict={}, cut_off: float=0.5, search_top:int=10):
        search_results = self.stepback_search(query, messages, doctype, filter, cut_off, search_top)
        result = self.llm.invoke([
            HumanMessage(
                content=[
                    {"type": "text", 
                     "text": GET_ANSWER_PROMPT.format(input=query, search_results=search_results, messages=messages)},
                ]
            )
        ])
        return result.content

    def get_available_tools(self):
        return [
            {
                "ref": self.index_documents,
                "name": "indexDocuments",
                "description": "Index documents in the vectorstore",
                "args_schema": IndexDocumentsModel
            },
            {
                "ref": self.search_documents,
                "name": "searchDocuments",
                "description": "Search documents in the vectorstore",
                "args_schema": SearchDocumentsModel
            },
            {
                "ref": self.stepback_search,
                "name": "stepbackSearch",
                "description": "Search in the vectorstore using stepback technique",
                "args_schema": StepBackSearchDocumentsModel
            },
            {
                "ref": self.stepback_summary,
                "name": "stepbackSummary",
                "description": "Get summary of search results using stepback technique",
                "args_schema": StepBackSearchDocumentsModel
            }
        ]
    
    def run(self, name: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == name:
                return tool["ref"](*args, **kwargs)
        else:
            raise ToolException(f"Unknown tool name: {name}")
