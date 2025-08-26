from typing import List, Literal, Optional
from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict
from pydantic.fields import Field

from .api_wrapper import GooglePlacesAPIWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length
from ...configurations.google_places import GooglePlacesConfiguration

name = "google_places"

def get_tools(tool):
    return GooglePlacesToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        results_count=tool['settings'].get('results_count'),
        google_places_configuration=tool['settings']['google_places_configuration'],
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()


class GooglePlacesToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in GooglePlacesAPIWrapper.model_construct().get_available_tools()}
        GooglePlacesToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            results_count=(Optional[int], Field(description="Results number to show", default=None, json_schema_extra={'toolkit_name': True, 'max_toolkit_length': GooglePlacesToolkit.toolkit_max_length})),
            google_places_configuration=(GooglePlacesConfiguration, Field(description="Google Places Configuration", json_schema_extra={'configuration_types': ['google_places']})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra=
                                  {
                                      'metadata':
                                          {
                                              "label": "Google Places", "icon_url": "gplaces-icon.svg",
                                              "categories": ["other"],
                                              "extra_categories": ["google", "places", "maps", "location",
                                                                   "geolocation"],
                                          }
                                  })
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('google_places_configuration', {}),
        }
        google_places_api_wrapper = GooglePlacesAPIWrapper(**wrapper_payload)
        prefix = clean_string(toolkit_name, GooglePlacesToolkit.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = google_places_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=google_places_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools
