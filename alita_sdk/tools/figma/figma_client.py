import json
from typing import Any, Dict, Optional

import requests
from FigmaPy import FigmaPy
from langchain_core.tools import ToolException


class AlitaFigmaPy(FigmaPy):
    """A thin wrapper over FigmaPy that exposes HTTP error details via ToolkitException.

    This class overrides ``api_request`` so that:
    - On 2xx responses it returns the parsed JSON body (same as the original).
    - On non-2xx responses it raises ``ToolkitException`` with status code and body
      instead of silently returning ``None``.
    """

    def api_request(self, endpoint: str, method: str = "get", payload: Optional[str] = None) -> Dict[str, Any]:
        method = method.lower()

        if payload is None:
            payload = ""

        if self.oauth2:
            header = {"Authorization": f"Bearer {self.api_token}"}
        else:
            header = {"X-Figma-Token": f"{self.api_token}"}

        header["Content-Type"] = "application/json"

        url = f"{self.api_uri}{endpoint}"

        try:
            if method == "head":
                response = requests.head(url, headers=header)
            elif method == "delete":
                response = requests.delete(url, headers=header)
            elif method == "get":
                response = requests.get(url, headers=header, data=payload)
            elif method == "options":
                response = requests.options(url, headers=header)
            elif method == "post":
                response = requests.post(url, headers=header, data=payload)
            elif method == "put":
                response = requests.put(url, headers=header, data=payload)
            else:
                raise ToolException(f"Unsupported HTTP method: {method}")

            # Happy path: 2xx -> return parsed JSON
            if 200 <= response.status_code < 300:
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    # Fallback: return raw text wrapped in a dict
                    return {"raw": response.text}

            # Error path: raise with as much context as we can
            try:
                data: Any = response.json()
            except ValueError:
                data = None

            message = response.text or f"HTTP {response.status_code} {response.reason}"

            # Build a detailed error string, since ToolException has no payload kwarg
            details = data or {"status": response.status_code, "message": message}
            raise ToolException(
                f"Figma API error {response.status_code}: {message}. Details: {details}"
            )

        except (requests.HTTPError, requests.exceptions.SSLError, requests.RequestException) as e:
            # Network / transport-level issues
            raise ToolException(f"Figma API request failed: {e}") from e
