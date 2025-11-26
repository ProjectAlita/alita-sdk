from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TestRailConfiguration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "metadata": {
                "label": "TestRail",
                "icon_url": "testrail.svg",
                "section": "credentials",
                "type": "testrail",
                "categories": ["test management"],
                "extra_categories": ["testrail", "test management", "quality assurance", "testing"],
            }
        }
    )
    url: str = Field(description="Testrail URL")
    email: str = Field(description="TestRail Email")
    password: SecretStr = Field(description="TestRail Password")

    @staticmethod
    def check_connection(settings: dict) -> str | None:
        """
        Check the connection to TestRail.
        
        Args:
            settings: Dictionary containing TestRail configuration
                - url: TestRail instance URL (required)
                - email: User email for authentication (required)
                - password: Password or API key for authentication (required)
        
        Returns:
            None if connection successful, error message string if failed
        """
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Validate url
        url = settings.get("url", "").strip()
        if not url:
            return "TestRail URL is required"
        
        # Normalize URL - remove trailing slashes
        url = url.rstrip("/")
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return "TestRail URL must start with http:// or https://"
        
        # Validate email
        email = settings.get("email", "").strip()
        if not email:
            return "TestRail email is required"
        
        # Validate password
        password = settings.get("password")
        if not password:
            return "TestRail password is required"
        
        # Extract password value if it's a SecretStr
        password_value = password.get_secret_value() if hasattr(password, 'get_secret_value') else password
        
        if not password_value or not password_value.strip():
            return "TestRail password cannot be empty"
        
        # Test connection using /index.php?/api/v2/get_user_by_email endpoint
        # This endpoint returns user info and validates authentication
        test_url = f"{url}/index.php?/api/v2/get_user_by_email&email={email}"
        
        try:
            response = requests.get(
                test_url,
                auth=HTTPBasicAuth(email, password_value),
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                # Successfully connected and authenticated
                return None
            elif response.status_code == 401:
                return "Authentication failed: invalid email or password"
            elif response.status_code == 403:
                return "Access forbidden: check user permissions"
            elif response.status_code == 404:
                return "TestRail API endpoint not found: verify the TestRail URL"
            elif response.status_code == 400:
                # Could be invalid email format or other bad request
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Bad request")
                    return f"Bad request: {error_msg}"
                except:
                    return "Bad request: check email format and URL"
            else:
                return f"TestRail API returned status code {response.status_code}"

        except requests.exceptions.SSLError as e:
            return f"SSL certificate verification failed: {str(e)}"
        except requests.exceptions.ConnectionError:
            return f"Cannot connect to TestRail at {url}: connection refused"
        except requests.exceptions.Timeout:
            return f"Connection to TestRail at {url} timed out"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to TestRail: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
