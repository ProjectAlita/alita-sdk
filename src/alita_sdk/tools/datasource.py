from typing import Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import create_model

datasourceToolSchema = create_model("datasourceSchema", query = (str, None))

class DatasourcePredict(BaseTool):
    name: str
    description: str
    datasource: Any
    
    def _run(self, query):
        result = self.datasource.predict(query)
        return f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    

class DatasourceSearch(BaseTool):
    name: str
    description: str
    datasource: Any
    
    def _run(self, query):
        result = self.datasource.search(query)
        return f"Search Results: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    
