import asyncio
from logging import getLogger
from typing import Any, Type, Literal, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

from src.alita_sdk.utils.serverio import callClient

logger = getLogger(__name__)

class McpTool(BaseTool):
    name: str
    description: str
    # Whether it's already established?
    socket_client: Any
    args_schema: Type[BaseModel] = None
    return_type: str = "str"

    @staticmethod
    def create_pydantic_model_from_schema(schema: dict):
        fields = {}
        for field_name, field_info in schema['properties'].items():
            field_type = field_info['type']
            field_description = field_info.get('description', '')
            if field_type == 'string':
                if 'enum' in field_info:
                    field_type = Literal[tuple(field_info['enum'])]
                else:
                    field_type = str
            elif field_type == 'integer':
                field_type = int
            elif field_type == 'number':
                field_type = float
            elif field_type == 'boolean':
                field_type = bool
            else:
                raise ValueError(f"Unsupported field type: {field_type}")

            if field_name in schema.get('required', []):
                fields[field_name] = (field_type, Field(..., description=field_description))
            else:
                fields[field_name] = (Optional[field_type], Field(None, description=field_description))
        return create_model('DynamicModel', **fields)
    
    def _run(self, *args, **kwargs):
        # socket connection?????
        # send event to socket per contract
        # socket_client.send_event(event=kwargs.get('event'), data=kwargs.get('data'))
        # wait for response

        # return f"Calling tool: \n{self.name} \n with kwargs: {kwargs}"

        response = asyncio.run(callClient({"query": "call_tools", "data": [
            dict(function=dict(name=self.name, arguments=kwargs), server="local-server-toolkit")]}))

        return response["content"]
