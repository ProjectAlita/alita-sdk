from typing import Any, Optional, Dict, Union

import requests
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from pydantic import model_validator, create_model, Field, PrivateAttr, SecretStr

from ...elitea_base import BaseToolApiWrapper

ERROR_PREFIX = 'Error:'

class AzureApiWrapper(BaseToolApiWrapper):
    subscription_id: str
    tenant_id: str
    client_id: str
    client_secret: SecretStr
    _credentials: Optional[ClientSecretCredential] = PrivateAttr()
    _client: Optional[ResourceManagementClient] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        subscription_id = values.get('subscription_id')
        tenant_id = values.get('tenant_id')
        client_id = values.get('client_id')
        client_secret = values.get('client_secret')
        cls._credentials = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        cls._client = ResourceManagementClient(cls._credentials, subscription_id)
        return values

    def execute(self, method: str, url: str, optional_args: Optional[Union[str, Dict[str, Any]]] = None):
        """ Executes an HTTP request to the Azure Resource Management REST API """
        request_args = self.json_query_load(optional_args)
        if url:
            if self.bad_domain(url):
                return self.bad_domain(url)
        else:
            return f"{ERROR_PREFIX} No url provided."
        token = self._credentials.get_token('https://management.azure.com/.default')
        headers = {
            'Authorization': 'Bearer ' + token.token,
        }
        if request_args is not None and 'headers' in request_args:
            request_args['headers'].update(headers)
        else:
            if request_args is None:
                request_args = {}
            request_args['headers'] = headers
        try:
            response = requests.request(method=method, url=url, **request_args)
            if response.status_code < 400:
                return str(response.text)
            else:
                return f"{ERROR_PREFIX} {response.status_code}, {response.text}"
        except Exception:
            return f"{ERROR_PREFIX} request failed"

    def azure_integration_healthcheck(self):
        """ Tests the integration with Azure by trying to access the resource groups with the provided credentials """
        try:
            resource_groups_url = f'https://management.azure.com/subscriptions/{self.subscription_id}/resourcegroups?api-version=2021-04-01'
            response = self.execute('GET', resource_groups_url)
            if response.startswith(ERROR_PREFIX):
                return False, response
        except Exception as e:
            return False, str(e)
        return True, ''

    def get_available_tools(self):
        return [
            {
                "name": "execute",
                "description": self.execute.__doc__,
                "args_schema": create_model(
                    "ExecuteModel",
                    method=(str, Field(description="The HTTP method to use for the request (GET, POST, PUT, DELETE, etc.). Required parameter.")),
                    url=(str, Field(description="Required parameter: always has FQDN part and protocol for Azure Resource Management REST API.")),
                    optional_args=(Optional[Union[str, Dict[str, Any]]], Field(description="Optional, valid json ONLY! No comments allowed. JSON object to be sent in request with possible keys: 'data', 'headers', 'files'.", default=None)),
                ),
                "ref": self.execute,
            },
            {
                "name": "azure_integration_healthcheck",
                "description": self.azure_integration_healthcheck.__doc__,
                "args_schema": create_model(
                    "AzureIntegrationHealthcheckModel",
                ),
                "ref": self.azure_integration_healthcheck,
            }
        ]