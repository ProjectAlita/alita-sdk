import json
import re
import logging
import yaml
from typing import List, Any, Optional, Dict
from langchain_core.tools import BaseTool, BaseToolkit, ToolException
from requests_openapi import Operation, Client, Server

from pydantic import create_model, Field
from functools import partial

logger = logging.getLogger(__name__)

name = "openapi"

def get_tools(tool):
    headers = {}
    if tool['settings'].get('authentication'):
        if tool['settings']['authentication']['type'] == 'api_key':
            auth_type = tool['settings']['authentication']['settings']['auth_type']
            auth_key = tool["settings"]["authentication"]["settings"]["api_key"]
            if auth_type.lower() == 'bearer':
                headers['Authorization'] = f'Bearer {auth_key}'
            if auth_type.lower() == 'basic':
                headers['Authorization'] = f'Basic {auth_key}'
            if auth_type.lower() == 'custom':
                headers[
                    tool["settings"]["authentication"]["settings"]["custom_header_name"]] = f'{auth_key}'
    return AlitaOpenAPIToolkit.get_toolkit(
        openapi_spec=tool['settings']['schema_settings'],
        selected_tools=tool['settings'].get('selected_tools', []),
        headers=headers).get_tools()


def create_api_tool(name: str, op: Operation):
    fields = {}
    headers = {}
    headers_descriptions = []

    for parameter in op.spec.parameters:
        if "header" in parameter.param_in:
            headers[parameter.name] = parameter.param_schema.default
            headers_descriptions.append(f"Header: {parameter.name}. Description: {parameter.description}.")
            continue
        fields[parameter.name] = (str, Field(default=parameter.param_schema.default,
                                             description=parameter.description))

    # add headers
    if headers:
        fields['headers'] = (Optional[dict], Field(default = headers, description="The dict that represents headers for request:\n" + '\n'.join(headers_descriptions)))

    if op.spec.requestBody:
        fields['json'] = (Optional[str], Field(default = None, description="JSON request body provided as a string"))

    op.server = Server.from_openapi_server(op.server)  # patch this
    op.server.get_url = partial(Server.get_url, op.server)
    op.server.set_url = partial(Server.set_url, op.server)
    return ApiTool(
        name=name,
        description=op.spec.description if op.spec.description else op.spec.summary,
        args_schema=create_model(
            'request_params',
            regexp = (Optional[str], Field(description="Regular expression used to remove from final output if any", default=None)),
            **fields),
        callable=op
    )

class ApiTool(BaseTool):
    name: str
    description: str
    callable: Operation

    def _run(self, regexp: str = None, **kwargs):
        # set in query parameter from header (actual for authentication)
        rq_args = self.args.keys()
        headers = self.callable.requestor.headers
        for arg in rq_args:
            arg_value = headers.get(arg)
            if arg_value:
                kwargs.update({arg : arg_value})

        if kwargs.get("json"):
            # add json to payload
            kwargs.update({"json": json.loads(kwargs.get("json"))})
        output = self.callable(**kwargs).content
        try:
            if regexp is not None:
                output = re.sub(rf'{regexp}', "", str(output))
        finally:
            return output

class AlitaOpenAPIToolkit(BaseToolkit):
    request_session: Any  #: :meta private:
    tools: List[BaseTool] = []

    @classmethod
    def get_toolkit(cls, openapi_spec: str | dict,
                    selected_tools: list[dict] | None = None,
                    headers: Optional[Dict[str, str]] = None):
        if selected_tools is not None:
            tools_set = set([i if not isinstance(i, dict) else i.get('name') for i in selected_tools])
        else:
            tools_set = {}
        if isinstance(openapi_spec, str):
            # Try to detect if it's YAML or JSON by attempting to parse as JSON first
            try:
                openapi_spec = json.loads(openapi_spec)
            except json.JSONDecodeError:
                # If JSON parsing fails, try YAML
                try:
                    openapi_spec = yaml.safe_load(openapi_spec)
                except yaml.YAMLError as e:
                    raise ToolException(f"Failed to parse OpenAPI spec as JSON or YAML: {e}")
        c = Client()
        c.load_spec(openapi_spec)
        if headers:
            c.requestor.headers.update(headers)
        tools = []
        for i in tools_set:

            try:
                if not i:
                    raise ToolException("Operation id is missing for some of declared operations.")
                tool = c.operations[i]
                if not isinstance(tool, Operation):
                    raise ToolException(f"Operation {i} is not an instance of Operation class.")
                tools.append(create_api_tool(i, tool))
            except ToolException:
                raise
            except Exception as e:
                logger.warning(f"Tool {i} not found in OpenAPI spec.")
                raise ToolException(f"Cannot create API tool ({i}): \n{e}.")
        return cls(request_session=c, tools=tools)

    def get_tools(self):
        return self.tools
