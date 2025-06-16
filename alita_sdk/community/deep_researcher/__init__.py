from .deep_research import DeepResearcher
from .iterative_research import IterativeResearcher
from .agents.baseclass import ResearchRunner
from .llm_config import LLMConfig

__all__ = ["DeepResearcher", "IterativeResearcher", "ResearchRunner", "LLMConfig"]

from typing import Any, List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import BaseModel, ConfigDict, create_model, Field

from .api_wrapper import DeepResearcherWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "deep_researcher"

def get_tools(tool):
    return DeepResearcherToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        max_iterations=tool['settings'].get('max_iterations', 5),
        max_time_minutes=tool['settings'].get('max_time_minutes', 10),
        verbose=tool['settings'].get('verbose', False),
        tracing=tool['settings'].get('tracing', False),
        alita=tool['settings'].get('alita', None),
        llm=tool['settings'].get('llm', None),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class DeepResearcherToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in DeepResearcherWrapper.model_construct().get_available_tools()}
        DeepResearcherToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            max_iterations=(int, Field(default=5, title="Max iterations", description="Maximum number of iterations for research", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': DeepResearcherToolkit.toolkit_max_length})),
            max_time_minutes=(int, Field(default=10, title="Max time (minutes)", description="Maximum time in minutes for research")),
            verbose=(bool, Field(default=False, title="Verbose", description="Print status updates to the console")),
            tracing=(bool, Field(default=False, title="Tracing", description="Enable tracing (only for OpenAI models)")),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Deep Researcher", "icon_url": "research-icon.svg"}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        deep_researcher_api_wrapper = DeepResearcherWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = deep_researcher_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=deep_researcher_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
