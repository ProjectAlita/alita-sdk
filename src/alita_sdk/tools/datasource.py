from ..clients.client import AlitaDataSource
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field


class DatasourceToolSchema(BaseModel):
    query: str = Field(description="The query to run against the datasource.")

class DatasourceAsATool(BaseTool):
    name: str
    description: str
    datasource: AlitaDataSource
    
    def _run(self, query):
        result = self.datasource.predict(query)
        return f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    
