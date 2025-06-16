from typing import List, Dict, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, create_model, Field

from .local_git import LocalGit
from .tool import LocalGitAction

name = "localgit"

def get_tools(tool):
    return AlitaLocalGitToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        repo_path=tool['settings'].get('repo_path', ''),
        base_path=tool['settings'].get('base_path', ''),
        repo_url=tool['settings'].get('repo_url', None),
        commit_sha=tool['settings'].get('commit_sha', None)
    ).get_tools()

class AlitaLocalGitToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in LocalGit.model_construct().get_available_tools()}
        return create_model(
            name,
            repo_path=(str, Field(default="", title="Repository path", description="Local GIT Repository path")),
            base_path=(str, Field(default="", title="Base path", description="Local GIT Base path")),
            repo_url=(Optional[str], Field(default=None, title="Repository URL", description="Local GIT Repository URL")),
            commit_sha=(Optional[str], Field(default=None, title="Commit SHA", description="Local GIT Commit SHA")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Local GIT", "icon_url": None, "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        local_git_tool = LocalGit(**kwargs)
        available_tools: List[Dict] = local_git_tool.get_available_tools()
        tools = []
        repo = local_git_tool.repo_path
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(LocalGitAction(
                api_wrapper=local_git_tool,
                name=repo + "_" + tool["name"],
                mode=tool["mode"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools