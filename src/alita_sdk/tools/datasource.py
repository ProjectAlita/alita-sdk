from typing import Any, Type, Dict, Optional
from langchain_core.tools import BaseTool
from pydantic import create_model, field_validator, BaseModel, ValidationInfo
from pydantic.fields import FieldInfo
from ..utils.utils import clean_string

datasourceToolSchema = create_model("datasourceSchema", query = (str, FieldInfo(description="search query")))

def get_query(args, kwargs):
    print(f"Kwargs: {kwargs}")
    if len(args) > 0:
        query = args[0]
    elif kwargs.get("input"):
        query = kwargs.get("input")
    else:
        query = kwargs.get('query', kwargs.get('messages'))
    if isinstance(query, list):
        query = query[-1].content
    print(f'The query for the datasource is: {query}')
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
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    current_state: Optional[dict] = None
    
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
        print(f'State in predict _run is - {kwargs}')
        if kwargs:
            result = self.datasource.predict(get_query(args, kwargs))
        else:
            result = self.datasource.predict(get_query(args, self.current_state))
        response = f"Response: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
        if kwargs.get("messages"):
            return process_response(response, self.return_type)
        else:
            if self.output_variables:
                return {self.output_variables[0]: response}
            else:
                return {'datasource_output': response}
    

class DatasourceSearch(BaseTool):
    name: str
    description: str
    datasource: Any
    args_schema: Type[BaseModel] = datasourceToolSchema
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    current_state: Optional[dict] = None
    
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
        result = self.datasource.search(get_query(args, self.current_state))
        response = f"Search Results: {result.content}\n\nReferences: {result.additional_kwargs['references']}"
        if kwargs.get("messages"):
            return process_response(response, self.return_type)
        else:
            return {'datasource_output': response}
    

