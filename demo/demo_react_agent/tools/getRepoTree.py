import requests
import logging
from typing import Type, Optional
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)

class getRepoTreeSchema(BaseModel):
    org: str = Field(description="The name of the organization that owns the repository.")
    repo: str = Field(description="The name of the repository.")
    branch: str = Field(default='main', description="The name of the branch to retrieve the tree structure from")
    recursive: str = Field(default='true', description="Whether to retrieve the tree structure recursively or not")
    

    
class getRepoTreeTool(BaseTool):
    name = "getRepoTree"
    description = "This API is used to retrieve the tree structure of a repository on GitHub."
    args_schema: Type[BaseModel] = getRepoTreeSchema
    
    def _run(self, org: str, repo: str, branch: Optional[str] = 'main', recursive: Optional[str] = 'true'):
        """This API is used to retrieve the tree structure of a repository on GitHub."""
        # Construct the API URL with the given parameters
        url = f"https://api.github.com/repos/{org}/{repo}/git/trees/{branch}?recursive={recursive}"
        logger.info(f"URL: {url}")
        # Include the 'recursive' parameter in the query string if requested
        
        try:
            # Send the GET request to the GitHub API
            response = requests.get(url, headers={"Content-Type": "application/json"})
            
            # Raise an exception if the request was unsuccessful
            response.raise_for_status()
            
            # Return the JSON response if the request was successful
            resp = response.json()
            # Retain only the "path" key in each item of the "tree" list
            paths = "\n - ".join([item["path"] for item in resp["tree"]])

            # Replace the original "tree" list with the filtered one
            logger.debug(f"Response: {paths}")
            return paths
        except requests.exceptions.HTTPError as http_err:
            return f"ERROR: HTTP error occurred: {http_err}"
        except Exception as err:
            return f"ERROR: An error occurred: {err}"