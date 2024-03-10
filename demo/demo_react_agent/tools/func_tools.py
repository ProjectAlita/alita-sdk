from langchain_core.tools import tool, StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
import requests
from os import path, makedirs, walk

def create_path_if_not_exists(file_path):
    if not path.exists(file_path):
        makedirs(file_path)

@tool
def storeSpecFile(file_name:str, file_content:str):
    """Stores the content of a file in the shared memory of the context."""
    # Add the file name and content to the shared memory of the context
    create_path_if_not_exists( "swaggers")
    with open(path.join( "swaggers", file_name), "w") as f:
        f.write(file_content)
    return f"Stored file swaggers/'{file_name}"

@tool
def getFolderContent(folder_path: str):
    """ Get listing of local file system files in a folder and its subfolder."""
    file_paths = []  # List to store file paths
    for root, _, files in walk(folder_path):
        for file in files:
            file_path = path.join(root, file)
            file_paths.append(file_path)
    return "\n".join(file_paths)


### StructuredTool example

class getRawFileSchema(BaseModel):
    org: str = Field(description="The name of the organization that owns the repository.")
    repo: str = Field(description="The name of the repository.")
    branch: str = Field(default='main', description="The name of the branch to retrieve the file from.")
    file_path: str = Field(description="The path of the file to retrieve.")

def getRawFile(org:str, repo:str, branch:str, file_path:str):
    """Fetches the content of a file in raw format from a specified GitHub repository, branch, and file path."""
    # Construct the URL for accessing the raw file content
    url = f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{file_path}"
    
    try:
        # Send the GET request to the GitHub Raw Content Server
        response = requests.get(url)
        
        # Raise an exception if the request was unsuccessful
        response.raise_for_status()
        
        # Return the text content of the response
        return response.text
    except requests.exceptions.HTTPError as http_err:
        return f"ERROR: HTTP error occurred: {http_err}"
    except Exception as err:
        return f"ERROR: An error occurred: {err}"

getRawFileTool = StructuredTool(
    name="getRawFile",
    description="Fetches the content of a file in raw format from a specified GitHub repository, branch, and file path.",
    func=getRawFile,
    args_schema=getRawFileSchema,
    verbose=True
)


class getFileContentSchema(BaseModel):
    file_path: str = Field(description="The path of the file to read.")

def getFileContent(file_path: str):
    """ Get the content of a file in of local file system."""
    try:
        with open(file_path, "r") as f:
            file_content = f.read()
        return file_content
    except Exception as e:
        return f"Error: {e}"
    
getFileContentTool = StructuredTool(
    name="getFileContent",
    description="Get the content of a file.",
    func=getFileContent,
    args_schema=getFileContentSchema,
    verbose=True
)