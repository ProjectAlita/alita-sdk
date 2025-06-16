import json
from typing import Any, Optional, List

from pydantic import BaseModel, Field, PrivateAttr, model_validator, create_model

import urllib3


class OpenApiConfig(BaseModel):
    spec: str
    api_key: str


class OpenApiWrapper(BaseModel):
    spec: str
    api_key: str
    _client: Optional[urllib3.PoolManager] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        cls._client = urllib3.PoolManager()
        return values

    def invoke_rest_api_by_spec(self, method: str, url: str, headers: str = "", fields: str = "", body: str = "") -> str:
        """
        Use this tool to invoke external API according to OpenAPI specification.
        If you do not have specification, retrieve it first by using another tool.
        All provided arguments must be in STRING format.
        You must provide the following required args: method: String, url: String.
        Other args are optional: fields: String, body: String.
        IMPORTANT: "fields" MUST be String text, example "fields": "{'param1': 'value'}"
        """
        encoded_data = body.encode('utf-8') if body else None
        headers_param = parse_to_dict(headers) if headers else {}
        fields_param = parse_to_dict(fields) if fields else None

        if self.api_key:
            headers_param['Authorization'] = "Bearer " + self.api_key

        response = self._client.request(method=method, url=url, fields=fields_param, headers=headers_param,
                                        body=encoded_data)
        return response.data.decode('utf-8')

    def get_open_api_spec(self) -> str:
        """
        Retrieves the OpenAPI (Swagger) specification for a given API endpoint. This tool helps in obtaining the necessary information to interact with an API using the "Invoke External API" tool.
        """
        return self.spec

    def get_available_tools(self):
        return [
            {
                "name": "invoke_rest_api_by_spec",
                "description": self.invoke_rest_api_by_spec.__doc__,
                "args_schema": create_model(
                    "InvokeRestApiBySpecModel",
                    method=(str, Field(description="The HTTP method to use")),
                    url=(str, Field(description="The URL to send the request to")),
                    headers=(Optional[str], Field(description="The headers to include in the request in JSON format", default="")),
                    fields=(Optional[str], Field(description="The query parameters to include in the request in JSON format", default="")),
                    body=(Optional[str], Field(description="The body of the request", default=""))
                ),
                "ref": self.invoke_rest_api_by_spec,
            },
            {
                "name": "get_open_api_spec",
                "description": self.get_open_api_spec.__doc__,
                "args_schema": create_model(
                    "GetOpenApiSpecModel",
                ),
                "ref": self.get_open_api_spec,
            }
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")


def parse_to_dict(input_string):
    try:
        # Try parsing it directly first, in case the string is already in correct JSON format
        parsed_dict = json.loads(input_string)
    except json.JSONDecodeError:
        # If that fails, replace single quotes with double quotes
        # and escape existing double quotes
        try:
            # This will convert single quotes to double quotes and escape existing double quotes
            adjusted_string = input_string.replace('\'', '\"').replace('\"', '\\\"')
            # If the above line replaces already correct double quotes, we correct them back
            adjusted_string = adjusted_string.replace('\\\"{', '\"{').replace('}\\\"', '}\"')
            # Now try to parse the adjusted string
            parsed_dict = json.loads(adjusted_string)
        except json.JSONDecodeError as e:
            # Handle any JSON errors
            print("JSON decode error:", e)
            return None
    return parsed_dict

