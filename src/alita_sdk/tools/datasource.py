from typing import Any, Type, Dict
from langchain_core.tools import BaseTool
from pydantic import create_model, field_validator, BaseModel, ValidationInfo
from pydantic.fields import FieldInfo
from ..utils.utils import clean_string

datasourceToolSchema = create_model("datasourceSchema", query = (str, FieldInfo(description="search query")))

def get_query(args, kwargs):
    if len(args) > 0:
        query = args[0]
    else:
        query = kwargs.get('query', kwargs.get('messages'))
    if isinstance(query, list):
        query = query[-1].content
    return query

def process_response(response, return_type):
    if return_type == "str":
        return response
    else:
        return {"messages": [{"role": "assistant", "content": response}]}

class DatasourcePredict(BaseTool):
    name: str
    description: str
    datasource: Any
    args_schema: Type[BaseModel] = datasourceToolSchema
    return_type: str = "str"
    
    @field_validator('query', mode='before', check_fields=False)
    @classmethod
    def remove_spaces_query(cls, v: str, info: ValidationInfo) -> str:
        if isinstance(v, Dict):
            return " ".join(list(v.values()))
        return v
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces_name(cls, v: str, info: ValidationInfo) -> str:
        return v.replace(' ', '')
    
    def _run(self, *args, **kwargs):
        result = self.datasource.predict(get_query(args, kwargs))
        response = f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
        return process_response(response, self.return_type)
    

class DatasourceSearch(BaseTool):
    name: str
    description: str
    datasource: Any
    args_schema: Type[BaseModel] = datasourceToolSchema
    return_type: str = "str"
    
    @field_validator('query', mode='before', check_fields=False)
    @classmethod
    def remove_spaces_query(cls, v):
        if isinstance(v, Dict):
            return " ".join(list(v.values()))
        return v
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces_name(cls, v):
        return clean_string(v)
    
    def _run(self, *args, **kwargs):
        result = self.datasource.search(get_query(args, kwargs))
        response = f"Search Results: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
        return process_response(response, self.return_type)
    

