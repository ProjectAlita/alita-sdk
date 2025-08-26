from functools import lru_cache
from typing import List, Optional, Type

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field, computed_field, field_validator

from ....configurations.bigquery import BigQueryConfiguration
from ...utils import TOOLKIT_SPLITTER, clean_string, get_max_toolkit_length
from .api_wrapper import BigQueryApiWrapper
from .tool import BigQueryAction

name = "bigquery"


@lru_cache(maxsize=1)
def get_available_tools() -> dict[str, dict]:
    api_wrapper = BigQueryApiWrapper.model_construct()
    available_tools: dict = {
        x["name"]: x["args_schema"].model_json_schema()
        for x in api_wrapper.get_available_tools()
    }
    return available_tools


toolkit_max_length = lru_cache(maxsize=1)(
    lambda: get_max_toolkit_length(get_available_tools())
)


class BigQueryToolkitConfig(BaseModel):
    class Config:
        title = name
        json_schema_extra = {
            "metadata": {
                "hidden": True,
                "label": "Cloud GCP",
                "icon_url": "google.svg",
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {"name": "API Key", "fields": ["api_key"]},
                        ],
                    }
                },
            }
        }

    bigquery_configuration: BigQueryConfiguration = Field(
        description="BigQuery configuration", json_schema_extra={"configuration_types": ["bigquery"]}
    )
    selected_tools: List[str] = Field(
        default=[],
        description="Selected tools",
        json_schema_extra={"args_schemas": get_available_tools()},
    )

    @field_validator("selected_tools", mode="before", check_fields=False)
    @classmethod
    def selected_tools_validator(cls, value: List[str]) -> list[str]:
        return [i for i in value if i in get_available_tools()]


def _get_toolkit(tool) -> BaseToolkit:
    return BigQueryToolkit().get_toolkit(
        selected_tools=tool["settings"].get("selected_tools", []),
        bigquery_configuration=tool["settings"]["bigquery_configuration"],
        toolkit_name=tool.get("toolkit_name"),
    )


def get_toolkit():
    return BigQueryToolkit.toolkit_config_schema()


def get_tools(tool):
    return _get_toolkit(tool).get_tools()


class BigQueryToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    api_wrapper: Optional[BigQueryApiWrapper] = Field(
        default_factory=BigQueryApiWrapper.model_construct
    )
    toolkit_name: Optional[str] = None

    @computed_field
    @property
    def tool_prefix(self) -> str:
        return (
            clean_string(self.toolkit_name, toolkit_max_length()) + TOOLKIT_SPLITTER
            if self.toolkit_name
            else ""
        )

    @computed_field
    @property
    def available_tools(self) -> List[dict]:
        return self.api_wrapper.get_available_tools()

    @staticmethod
    def toolkit_config_schema() -> Type[BaseModel]:
        return BigQueryToolkitConfig

    @classmethod
    def get_toolkit(
        cls,
        selected_tools: list[str] | None = None,
        toolkit_name: Optional[str] = None,
        **kwargs,
    ) -> "BigQueryToolkit":
        wrapper_payload = {
            **kwargs,
            # TODO use bigquery_configuration fields
            **kwargs['bigquery_configuration'],
        }
        bigquery_api_wrapper = BigQueryApiWrapper(**wrapper_payload)
        instance = cls(
            tools=[], api_wrapper=bigquery_api_wrapper, toolkit_name=toolkit_name
        )
        if selected_tools:
            selected_tools = set(selected_tools)
            for t in instance.available_tools:
                if t["name"] in selected_tools:
                    instance.tools.append(
                        BigQueryAction(
                            api_wrapper=instance.api_wrapper,
                            name=instance.tool_prefix + t["name"],
                            # set unique description for declared tools to differentiate the same methods for different toolkits
                            description=f"Project: {getattr(instance.api_wrapper, 'project', '')}\n"
                            + t["description"],
                            args_schema=t["args_schema"],
                        )
                    )
        return instance

    def get_tools(self):
        return self.tools