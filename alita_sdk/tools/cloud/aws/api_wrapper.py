from typing import Optional, Dict, Any, Union

import boto3
from botocore.config import Config
from pydantic import Field, PrivateAttr, create_model, model_validator, SecretStr

from ...elitea_base import BaseToolApiWrapper


class AWSToolConfig(BaseToolApiWrapper):
    region: str
    access_key_id: Optional[str] = None
    secret_access_key: Optional[SecretStr] = None
    _client: Optional[boto3.client] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        region = values.get('region')
        access_key_id = values.get('access_key_id')
        secret_access_key = values.get('secret_access_key')
        client_config = Config(region_name=region)
        cls._client = boto3.client(
            'service',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=client_config
        )
        return values

    def execute_aws(self, query: Union[str, Dict[str, Any]]):
        """Execute AWS service method based on the provided query"""
        loaded = self.json_query_load(query)
        if 'service' in loaded:
            api_instance = self._client(service=loaded["service"])
            response = getattr(api_instance, loaded["method_name"])(**loaded["method_arguments"])
            return str(response)

    def json_query_load(self, query: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(query, str):
            import json
            return json.loads(query)
        return query

    def get_available_tools(self):
        return [
            {
                "name": "execute_aws",
                "ref": self.execute_aws,
                "description": self.execute_aws.__doc__,
                "args_schema": create_model(
                    "AWSExecuteModel",
                    query=(Union[str, Dict[str, Any]], Field(description="Query to execute AWS service method"))
                ),
            }
        ]