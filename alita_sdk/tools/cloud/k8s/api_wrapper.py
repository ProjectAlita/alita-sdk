import json
from typing import Tuple, Optional, Dict, Any, Union

from kubernetes import client, config as k8s_config
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict, model_validator, create_model, SecretStr

from ...elitea_base import BaseToolApiWrapper


class KubernetesApiWrapper(BaseToolApiWrapper):
    url: str
    token: Optional[SecretStr] = None
    _client: Optional[client.CoreV1Api] = PrivateAttr()
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        url = values.get('url')
        token = values.get('token')
        if url and token:
            configuration = client.Configuration()
            configuration.host = url
            configuration.verify_ssl = False
            configuration.api_key = {'authorization': 'Bearer ' + token}
            cls._client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            k8s_config.load_kube_config()
            cls._client = client.CoreV1Api()
        return values

    def execute_kubernetes(self, method: str, suburl: str, body: Optional[Union[str, Dict[str, Any]]] = None, headers: Optional[Union[str, Dict[str, Any]]] = None) -> str:
        """
        Execute a Kubernetes API request with the specified method, suburl, body, and headers.
        """
        try:
            if headers:
                headers = json.loads(headers)
            if body:
                body = json.loads(body)
                response = self._client.api_client.call_api(suburl, method, body=body,
                                                            header_params=headers,
                                                            auth_settings=['BearerToken'], response_type='json',
                                                            _preload_content=False)
            else:
                response = self._client.api_client.call_api(suburl, method,
                                                            header_params=headers,
                                                            auth_settings=['BearerToken'], response_type='json',
                                                            _preload_content=False)
        except Exception as e:
            return f"Error: {e}"
        try:
            if response[1] == 200:
                return response[0].data.decode('utf-8')
            elif response[0].data.decode('utf-8'):
                return response[0].data.decode('utf-8')
            else:
                return f"Error: {response[0]}"
        except Exception:
            return "Tool output parsing error"

    def kubernetes_integration_healthcheck(self) -> Tuple[bool, str]:
        """
        Tests the integration with a Kubernetes cluster by performing a GET request to a predefined URL.

        This method attempts to verify the connectivity and authentication against a Kubernetes cluster
        using provided URL and token parameters. In the case of successful response tool will return the
        JSON body of that response. In other case tool will return string representation of unsuccessful
        response (or exception) which cannot be decoded as JSON.

        Parameters:
        - url (str): The URL of the Kubernetes cluster to test integration with.
        - token (str, optional): The authentication token used for accessing the Kubernetes cluster. If not
                                 provided, no token will be used.

        Returns:
        - Tuple[bool, str]: A tuple containing a boolean and a string. The boolean indicates the success
                            status of the integration test (True for success, False for failure). The string
                            contains an error message in case of failure or an empty string "" in case of
                            success.
        """
        response = self.execute_kubernetes("GET", "/version")

        try:
            json.loads(response)
        except json.JSONDecodeError:
            return False, response
        return True, ""

    def get_available_tools(self):
        return [
            {
                "name": "execute_kubernetes",
                "description": self.execute_kubernetes.__doc__,
                "args_schema": create_model(
                    "ExecuteToolModel",
                    method=(str, Field(description="The HTTP method to use for the request (GET, POST, PUT, DELETE, etc.).")),
                    suburl=(str, Field(description="The relative URI for Kubernetes API. URI must start with a forward slash , example '/api/v1/...'. Do not include query parameters in the URL, they must be provided separately in 'body'.")),
                    body=(Optional[Union[str, Dict[str, Any]]], Field(description="Optional JSON object to be sent in request body. No comments allowed.", default=None)),
                    headers=(Optional[Union[str, Dict[str, Any]]], Field(description="Optional JSON object of headers to be sent in request. No comments allowed.", default=None))
                ),
                "ref": self.execute_kubernetes,
            },
            {
                "name": "kubernetes_integration_healthcheck",
                "description": self.kubernetes_integration_healthcheck.__doc__,
                "args_schema": create_model(
                    "KubernetesIntegrationHealthcheckModel"
                ),
                "ref": self.kubernetes_integration_healthcheck,
            }
        ]