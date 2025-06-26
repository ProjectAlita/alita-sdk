from typing import Dict, List, Optional, Literal, Any

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import create_model, BaseModel, ConfigDict, Field, SecretStr

from .api_wrapper import AlitaGitHubAPIWrapper
from .tool import GitHubAction

from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "github"

def _get_toolkit(tool) -> BaseToolkit:
    return AlitaGitHubToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        github_base_url=tool['settings'].get('base_url', ''),
        github_repository=tool['settings']['repository'],
        active_branch=tool['settings']['active_branch'],
        github_base_branch=tool['settings']['base_branch'],
        github_access_token=tool['settings'].get('access_token', ''),
        github_username=tool['settings'].get('username', ''),
        github_password=tool['settings'].get('password', ''),
        github_app_id=tool['settings'].get('app_id', None),
        github_app_private_key=tool['settings'].get('app_private_key', None),
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        connection_string=tool['settings'].get('connection_string', None),
        collection_name=str(tool['id']),
        doctype='code',
        embedding_model="HuggingFaceEmbeddings",
        embedding_model_params={"model_name": "sentence-transformers/all-MiniLM-L6-v2"},
        vectorstore_type="PGVector",
        toolkit_name=tool.get('toolkit_name')
    )

def get_toolkit():
    return AlitaGitHubToolkit.toolkit_config_schema()

def get_tools(tool):
    return _get_toolkit(tool).get_tools()

class AlitaGitHubToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in AlitaGitHubAPIWrapper.model_construct().get_available_tools()}
        AlitaGitHubToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            __config__=ConfigDict(
                json_schema_extra={
                    'metadata': {
                        "label": "GitHub",
                        "icon_url": None,
                        "sections": {
                            "auth": {
                                "required": False,
                                "subsections": [
                                    {
                                        "name": "Token",
                                        "fields": ["access_token"]
                                    },
                                    {
                                        "name": "Password",
                                        "fields": ["username", "password"]
                                    },
                                    {
                                        "name": "App private key",
                                        "fields": ["app_id", "app_private_key"]
                                    }
                                ]
                            },
                        },
                        "categories": ["code repositories"],
                        "extra_categories": ["github", "git", "repository", "code", "version control"],
                    },
                }
            ),
            base_url=(Optional[str], Field(description="Base API URL", default="https://api.github.com", json_schema_extra={'configuration': True, 'configuration_title': True})),
            app_id=(Optional[str], Field(description="Github APP ID", default=None, json_schema_extra={'configuration': True})),
            app_private_key=(Optional[SecretStr], Field(description="Github APP private key", default=None, json_schema_extra={'secret': True, 'configuration': True})),

            access_token=(Optional[SecretStr], Field(description="Github Access Token", default=None, json_schema_extra={'secret': True, 'configuration': True})),

            username=(Optional[str], Field(description="Github Username", default=None, json_schema_extra={'configuration': True})),
            password=(Optional[SecretStr], Field(description="Github Password", default=None, json_schema_extra={'secret': True, 'configuration': True})),

            repository=(str, Field(description="Github repository", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AlitaGitHubToolkit.toolkit_max_length})),
            active_branch=(Optional[str], Field(description="Active branch", default="main")),
            base_branch=(Optional[str], Field(description="Github Base branch", default="main")),
            
            # indexer settings
            connection_string = (Optional[SecretStr], Field(description="Connection string for vectorstore",
                                                            default=None,
                                                            json_schema_extra={'secret': True})),
            
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools}))
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        github_api_wrapper = AlitaGitHubAPIWrapper(**kwargs)
        available_tools: List[Dict] = github_api_wrapper.get_available_tools()
        tools = []
        prefix = clean_string(toolkit_name, AlitaGitHubToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(GitHubAction(
                api_wrapper=github_api_wrapper,
                name=prefix + tool["name"],
                mode=tool["mode"],
                # set unique description for declared tools to differentiate the same methods for different toolkits
                description=f"Repository: {github_api_wrapper.github_repository}\n" + tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools

