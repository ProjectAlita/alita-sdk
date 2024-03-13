from ..clients.client import AlitaDataSource
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import AnyStr

class DatasourceToolSchema(BaseModel):
    query: AnyStr = Field(description="The query to run against the datasource.")

class DatasourcePredict(BaseTool):
    name: str
    description: str
    datasource: AlitaDataSource
    
    def _run(self, query):
        result = self.datasource.predict(query)
        return f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    

class DatasourceSearch(BaseTool):
    name: str
    description: str
    datasource: AlitaDataSource
    
    def _run(self, query):
        result = self.datasource.search(query)
        return f"Search Results: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    
