from typing import List, Literal, Optional, Dict, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from .api_wrapper import BrowserUseAPIWrapper
from langchain_core.tools import BaseTool
from alita_tools.base.tool import BaseAction
from pydantic import create_model, BaseModel, ConfigDict, Field
from alita_tools.utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "browser_use"

def get_tools(tool):
    return BrowserUseToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        headless=tool['settings'].get('headless', True),
        width=tool['settings'].get('width', 1280),
        height=tool['settings'].get('height', 800),
        cookies=tool['settings'].get('cookies', None),
        disable_security=tool['settings'].get('disable_security', True),
        proxy=tool['settings'].get('proxy', None),
        extra_chromium_args=tool['settings'].get('extra_chromium_args', []),
        bucket=tool['settings'].get('bucket', None),
        alita=tool['settings'].get('alita'),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

toolkit_max_length = 25

class BrowserUseToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in
                          BrowserUseAPIWrapper.model_construct().get_available_tools()}
        return create_model(
            name,
            headless=(bool, Field(description="Run browser in headless mode", default=True)),
            width=(int, Field(description="Browser window width", default=1280)),
            height=(int, Field(description="Browser window height", default=800)),
            bucket=(Optional[str], Field(description="Bucket to store test results", default=None)),
            cookies=(Optional[Dict[str, Any]], Field(description="Browser cookies as JSON", default=None)),
            disable_security=(bool, Field(description="Disable browser security features", default=True)),
            proxy=(Optional[Dict[str, str]], Field(description="Proxy settings", default=None)),
            extra_chromium_args=(List[str], Field(description="Extra arguments to pass to the browser", default=[])),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                           Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "Browser Use", "icon_url": None, "hidden": True}})
        )
    
    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        _api_wrapper = BrowserUseAPIWrapper(**kwargs)
        prefix = clean_string(toolkit_name, toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = _api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(
                BaseAction(
                    api_wrapper=_api_wrapper,
                    name=prefix + tool["name"],
                    description=f"Browser automation tool: {tool['name']}" + tool["description"],
                    args_schema=tool["args_schema"],
                )
            )
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
