import uuid
from logging import getLogger
from typing import Any, Type, Literal, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

logger = getLogger(__name__)


class McpServerTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    return_type: str = "str"
    client: Any
    server: str
    tool_timeout_sec: int = 60


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
            elif field_type == 'object':#Dict[str, Any]
                nested_model = McpServerTool.create_pydantic_model_from_schema(field_info)
                field_type = nested_model
            elif field_type == 'array':
                item_schema = field_info['items']
                item_type = McpServerTool.create_pydantic_model_from_schema(item_schema) if item_schema['type'] == 'object' else (
                    str if item_schema['type'] == 'string' else
                    int if item_schema['type'] == 'integer' else
                    float if item_schema['type'] == 'number' else
                    bool if item_schema['type'] == 'boolean' else
                    None
                )
                if item_type is None:
                    raise ValueError(f"Unsupported array item type: {item_schema['type']}")
                field_type = list[item_type]
            else:
                raise ValueError(f"Unsupported field type: {field_type}")

            if field_name in schema.get('required', []):
                fields[field_name] = (field_type, Field(..., description=field_description))
            else:
                fields[field_name] = (Optional[field_type], Field(None, description=field_description))
        return create_model('DynamicModel', **fields)

    def _run(self, *args, **kwargs):
        call_data = {
            "server": self.server,
            "tool_timeout_sec": self.tool_timeout_sec,
            "tool_call_id": str(uuid.uuid4()),
            "params": {
                "name": self.name,
                "arguments": kwargs
            }
        }
        
        return self.client.mcp_tool_call(call_data)
