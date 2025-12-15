from json import JSONDecodeError
from typing import Optional

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr


def _parse_error_response(response: requests.Response) -> Optional[str]:
    """
    Parse error response from Figma API to extract detailed error message.

    Args:
        response: Response object from requests

    Returns:
        Detailed error message if found, None otherwise
    """
    try:
        json_response = response.json()
        error = json_response.get("err") or json_response.get("error")
        if error and 'Invalid token' in str(error):
            return "Invalid token. Please verify the Figma token and try again."
    except (JSONDecodeError, KeyError, AttributeError):
        pass
    return None


class FigmaConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "Figma",
                "icon_url": "figma-icon.svg",
                "sections": {
                    "auth": {
                        "required": True,
                        "subsections": [
                            {
                                "name": "Token",
                                "fields": ["token"]
                            }
                        ]
                    }
                },
                "section": "credentials",
                "type": "figma",
                "categories": ["other"],
                "extra_categories": ["figma", "design", "ui/ux", "prototyping", "collaboration"],
            }
        }
    )
    token: Optional[SecretStr] = Field(description="Figma Token", json_schema_extra={"secret": True}, default=None)

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Test the connection to Figma API.

        Args:
            settings: Dictionary containing 'token' (required)

        Returns:
            None if connection is successful, error message string otherwise
        """
        token = settings.get("token")
        if token is None:
            return "Token is required"

        # Extract secret value if it's a SecretStr
        if hasattr(token, "get_secret_value"):
            token = token.get_secret_value()

        # Validate token is not empty
        if not token or not token.strip():
            return "Token cannot be empty"

        # Figma API endpoint
        base_url = "https://api.figma.com"
        endpoint = f"{base_url}/v1/me"

        try:
            response = requests.get(
                endpoint,
                headers={"X-Figma-Token": token},
                timeout=10,
            )

            if response.status_code == 200:
                return None  # Connection successful
            elif response.status_code == 401:
                detailed_error = _parse_error_response(response)
                return detailed_error if detailed_error else "Invalid token"
            elif response.status_code == 403:
                detailed_error = _parse_error_response(response)
                return detailed_error if detailed_error else "Access forbidden - token may lack required permissions"
            else:
                return f"Connection failed with status {response.status_code}"

        except requests.exceptions.Timeout:
            return "Connection timeout - Figma API is not responding"
        except requests.exceptions.ConnectionError:
            return "Connection error - unable to reach Figma API"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
