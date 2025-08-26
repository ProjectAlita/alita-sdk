from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import SQLApiWrapper
from ..base.tool import BaseAction
from .models import SQLDialect
from ..utils import TOOLKIT_SPLITTER, clean_string, get_max_toolkit_length
from ...configurations.sql import SqlConfiguration

name = "sql"

def get_tools(tool):
    return SQLToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        dialect=tool['settings']['dialect'],
        database_name=tool['settings']['database_name'],
        sql_configuration=tool['settings']['sql_configuration'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class SQLToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in SQLApiWrapper.model_construct().get_available_tools()}
        SQLToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        supported_dialects = (d.value for d in SQLDialect)
        return create_model(
            name,
            dialect=(Literal[tuple(supported_dialects)], Field(description="Database dialect (mysql or postgres)")),
            database_name=(str, Field(description="Database name", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': SQLToolkit.toolkit_max_length})),
            sql_configuration=(SqlConfiguration, Field(description="SQL Configuration", json_schema_extra={'configuration_types': ['sql']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra=
                                  {
                                      'metadata':
                                          {
                                              "label": "SQL", "icon_url": "sql-icon.svg",
                                              "categories": ["development"],
                                              "extra_categories": ["sql", "data management", "data analysis"]}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('sql_configuration', {}),
        }
        sql_api_wrapper = SQLApiWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = sql_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=sql_api_wrapper,
                name=prefix + tool["name"],
                description=f"{tool['description']}\nDatabase: {sql_api_wrapper.database_name}. Host: {sql_api_wrapper.host}",
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools
