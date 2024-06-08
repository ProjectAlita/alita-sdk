from typing import Any, Type
from langchain.tools import BaseTool
from pydantic import create_model, validator, BaseModel
from pydantic.fields import FieldInfo

datasourceToolSchema = create_model("datasourceSchema", query = (str, FieldInfo(description="search query")))

class DatasourcePredict(BaseTool):
    name: str
    description: str
    datasource: Any
    args_schema: Type[BaseModel] = datasourceToolSchema
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return v.replace(' ', '')
    
    
    def _run(self, query):
        result = self.datasource.predict(query)
        return f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    

class DatasourceSearch(BaseTool):
    name: str
    description: str
    datasource: Any
    args_schema: Type[BaseModel] = datasourceToolSchema
    
    @validator('name', pre=True, allow_reuse=True)
    def remove_spaces(cls, v):
        return v.replace(' ', '')
    
    def _run(self, query):
        result = self.datasource.search(query)
        return f"Search Results: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
    
