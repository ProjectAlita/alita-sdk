import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, PrivateAttr, model_validator, SecretStr
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from langchain_openai import AzureOpenAIEmbeddings

from ...elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

class AzureSearchInput(BaseModel):
    search_text: str = Field(..., description="The text to search for in the Azure Search index.")
    limit: int = Field(10, description="The number of results to return.")
    selected_fields: Optional[List[str]] = Field(None, description="The fields to retrieve from the document.")

class AzureDocumentInput(BaseModel):
    document_id: str = Field(description="The ID of the document to retrieve.")
    selected_fields: Optional[List[str]] = Field(None, description="The fields to retrieve from the document.")

class TextSearchInput(BaseModel):
    search_text: str = Field(description="The text to search for in the Azure Search index.")
    limit: Optional[int] = Field(-1, description="The number of results to return (if no limit needed use -1).")
    order_by: Optional[List[str]] = Field(None, description="Ordering expression for the search results (if no order needed use empty list).")
    selected_fields: Optional[List[str]] = Field(None, description="The fields to retrieve from the document (if no fields needed use empty list).")

class VectorSearchInput(BaseModel):
    vectors: List[Dict[str, Any]] = Field(..., description="The vectors to search for in the Azure Search index.")
    limit: Optional[int] = Field(None, description="The number of results to return.")

class HybridSearchInput(BaseModel):
    search_text: str = Field(..., description="The text to search for in the Azure Search index.")
    vectors: List[Dict[str, Any]] = Field(..., description="The vectors to search for in the Azure Search index.")
    limit: Optional[int] = Field(None, description="The number of results to return.")

class AzureSearchApiWrapper(BaseToolApiWrapper):
    _client: Any = PrivateAttr()
    _AzureOpenAIClient: Any = PrivateAttr()
    api_key: SecretStr
    endpoint: str
    index_name: str
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    openai_api_key: Optional[SecretStr] = None
    model_name: Optional[str] = None
    

    @model_validator(mode='before')
    @classmethod
    def validate_fields(cls, values):
        if not values.get('api_key'):
            raise ValueError("API key is required.")
        if not values.get('endpoint'):
            raise ValueError("Endpoint is required.")
        if not values.get('index_name'):
            raise ValueError("Index name is required.")
        
        cls._client = SearchClient(
            endpoint=values['endpoint'],
            index_name=values['index_name'],
            credential=AzureKeyCredential(values['api_key'])
        )
        if values.get('openai_api_key') and values.get('model_name'):
            cls._AzureOpenAIClient = AzureOpenAIEmbeddings(
                model=values['model_name'],
                api_version=values['api_version'],
                azure_endpoint=values['api_base'],
                api_key=values['openai_api_key'],
            )
        return values

    def text_search(self, search_text: str, limit: Optional[int] = -1, order_by: Optional[List[str]] = None, selected_fields: Optional[list] = []) -> List[Dict]:
        """
        Perform a search query on the Azure Search index.

        :param search_text: The text to search for in the Azure Search index.
        :param limit: The number of results to return (if no limit needed use -1)
        :param order_by: Ordering expression for the search results (if no order needed use empty list).
        :param selected_fields: The fields to retrieve from the document (if no fields needed use empty list).
        :return: A list of search results.
        """
        if limit == -1:
            limit = None
        if selected_fields and len(selected_fields) == 0:
            selected_fields = None
        if order_by and len(order_by) == 0:
            order_by = None
        results = self._client.search(search_text=search_text, top=limit, order_by=order_by, select=selected_fields)
        return list(results)

    def get_document(self, document_id: str, selected_fields: Optional[list] = None) -> Dict[str, Any]:
        """
        Get a specific document from the Azure Search index.

        :param document_id: The ID of the document to retrieve.
        :param selected_fields: The fields to retrieve from the document.
        :return: The document.
        """
        if selected_fields and len(selected_fields) == 0:
            selected_fields = None
        return self._client.get_document(key=document_id, selected_fields=selected_fields)


    def vector_search(self, vectors: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Perform a vector search query on the Azure Search index.

        :param vectors: The vectors to search for in the Azure Search index.
        :param limit: The number of results to return.
        :return: A list of search results.
        """
        results = self._client.search(vector_queries=vectors)
        res = list(results)
        if limit is None or limit == -1:
            return res
        else:
            return res[:limit]

    def hybrid_search(self, search_text: str, vectors: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Perform a hybrid search query on the Azure Search index.

        :param search_text: The text to search for in the Azure Search index.
        :param vectors: The vectors to search for in the Azure Search index.
        :param limit: The number of results to return.
        :return: A list of search results.
        """
        results = self._client.search(search_text=search_text, vector_queries=vectors)
        res = list(results)
        if limit is None or limit == -1:
            return res
        else:
            return res[:limit]

    def get_available_tools(self):
        """
        Get the available tools for the Azure Search API.

        :return: A list of available tools.
        """
        return [
            {
                "name": "text_search",
                "ref": self.text_search,
                "description": self.text_search.__doc__,
                "args_schema": TextSearchInput,
            },
            # {
            #     "name": "vector_search",
            #     "ref": self.vector_search,
            #     "description": self.vector_search.__doc__,
            #     "args_schema": VectorSearchInput,
            # },
            # {
            #     "name": "hybrid_search",
            #     "ref": self.hybrid_search,
            #     "description": self.hybrid_search.__doc__,
            #     "args_schema": HybridSearchInput,
            # },
            {
                "name": "get_document",
                "ref": self.get_document,
                "description": self.get_document.__doc__,
                "args_schema": AzureDocumentInput,
            },
        ]