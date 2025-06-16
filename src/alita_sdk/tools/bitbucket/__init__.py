from typing import Dict, List, Literal, Optional
from .api_wrapper import BitbucketAPIWrapper
from .tools import __all__
from langchain_core.tools import BaseToolkit
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict, create_model, SecretStr
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length


name = "bitbucket"


def get_tools(tool):
    return AlitaBitbucketToolkit.get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        url=tool['settings']['url'],
        project=tool['settings']['project'],
        repository=tool['settings']['repository'],
        username=tool['settings']['username'],
        password=tool['settings']['password'],
        branch=tool['settings']['branch'],
        cloud=tool['settings'].get('cloud'),
        toolkit_name=tool.get('toolkit_name'),
    ).get_tools()


class AlitaBitbucketToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {}
        for t in __all__:
            default = t['tool'].__pydantic_fields__['args_schema'].default
            selected_tools[t['name']] = default.schema() if default else default
        AlitaBitbucketToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            url=(str, Field(description="Bitbucket URL")),
            project=(str, Field(description="Project/Workspace")),
            repository=(str, Field(description="Repository", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': AlitaBitbucketToolkit.toolkit_max_length})),
            branch=(str, Field(description="Main branch", default="main")),
            username=(str, Field(description="Username")),
            password=(SecretStr, Field(description="GitLab private token", json_schema_extra={'secret': True})),
            cloud=(Optional[bool], Field(description="Hosting Option", default=None)),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Bitbucket", "icon_url": "bitbucket-icon.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        if kwargs["cloud"] is None:
            kwargs["cloud"] = True if "bitbucket.org" in kwargs.get('url') else False
        bitbucket_api_wrapper = BitbucketAPIWrapper(**kwargs)
        available_tools: List[Dict] = __all__
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool['name'] not in selected_tools:
                    continue
            initiated_tool = tool['tool'](api_wrapper=bitbucket_api_wrapper)
            initiated_tool.name = prefix + tool['name']
            tools.append(initiated_tool)
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
