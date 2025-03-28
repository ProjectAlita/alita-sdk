from datetime import time
from logging import getLogger
from typing import Type, Literal, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

from src.alita_sdk.clients import AlitaClient

logger = getLogger(__name__)

class McpTool(BaseTool):
    name: str
    description: str
    alita: AlitaClient  # This should be the client to interact with the backend
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
        # send API call to BE: start tool execution (uuid???, tool name, tool params)
        # exec_data = self.alita.start_tool(uuid=room_uuid, tool_name=self.name, params=kwargs)
        # get execution status from BE and wait until it's done
        # return self._wait_for_execution(exec_data['call_id'])

        # return tool's execution result
        return f"Calling tool: \n{self.name} \n with kwargs: {kwargs}"

    def _wait_for_execution(self, call_id, polling_interval=20) -> str:
        """
        Wait for the tool execution to finish and return the final output.
        """
        exec_data = {'call_id': call_id}
        status = self.alita.get_mcp_tool_state(call_id=exec_data['call_id'])

        while status['status'] not in ['success', 'error']:
            logger.info(f"Tool execution status: {status['status']}")
            time.sleep(polling_interval)
            status = self.alita.get_mcp_tool_state(call_id=exec_data['call_id'])['status']
        return status['final_output']
