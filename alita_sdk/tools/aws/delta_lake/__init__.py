
from functools import lru_cache
from typing import List, Optional, Type

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field, computed_field, field_validator

from alita_sdk.configurations.delta_lake import DeltaLakeConfiguration
from ...utils import TOOLKIT_SPLITTER, clean_string, get_max_toolkit_length
from .api_wrapper import DeltaLakeApiWrapper
from .tool import DeltaLakeAction

name = "delta_lake"

@lru_cache(maxsize=1)
def get_available_tools() -> dict[str, dict]:
    api_wrapper = DeltaLakeApiWrapper.model_construct()
    available_tools: dict = {
        x["name"]: x["args_schema"].model_json_schema()
        for x in api_wrapper.get_available_tools()
    }
    return available_tools

toolkit_max_length = lru_cache(maxsize=1)(
    lambda: get_max_toolkit_length(get_available_tools())
)

class DeltaLakeToolkitConfig(BaseModel):
    class Config:
        title = name
        json_schema_extra = {
            "metadata": {
                "hidden": True,
                "label": "AWS Delta Lake",
                "icon_url": "delta-lake.svg",
                "sections": {
                    "auth": {
                        "required": False,
                        "subsections": [
                            {"name": "AWS Access Key ID", "fields": ["aws_access_key_id"]},
                            {"name": "AWS Secret Access Key", "fields": ["aws_secret_access_key"]},
                            {"name": "AWS Session Token", "fields": ["aws_session_token"]},
                            {"name": "AWS Region", "fields": ["aws_region"]},
                        ],
                    },
                    "connection": {
                        "required": False,
                        "subsections": [
                            {"name": "Delta Lake S3 Path", "fields": ["s3_path"]},
                            {"name": "Delta Lake Table Path", "fields": ["table_path"]},
                        ],
                    },
                },
            }
        }

    delta_lake_configuration: DeltaLakeConfiguration = Field(description="Delta Lake Configuration", json_schema_extra={"configuration_types": ["delta_lake"]})
    selected_tools: List[str] = Field(default=[], description="Selected tools", json_schema_extra={"args_schemas": get_available_tools()})

    @field_validator("selected_tools", mode="before", check_fields=False)
    @classmethod
    def selected_tools_validator(cls, value: List[str]) -> list[str]:
        return [i for i in value if i in get_available_tools()]

def _get_toolkit(tool) -> BaseToolkit:
    return DeltaLakeToolkit().get_toolkit(
        selected_tools=tool["settings"].get("selected_tools", []),
        aws_access_key_id=tool["settings"].get("delta_lake_configuration").get("aws_access_key_id", None),
        aws_secret_access_key=tool["settings"].get("delta_lake_configuration").get("aws_secret_access_key", None),
        aws_session_token=tool["settings"].get("delta_lake_configuration").get("aws_session_token", None),
        aws_region=tool["settings"].get("delta_lake_configuration").get("aws_region", None),
        s3_path=tool["settings"].get("delta_lake_configuration").get("s3_path", None),
        table_path=tool["settings"].get("delta_lake_configuration").get("table_path", None),
        toolkit_name=tool.get("toolkit_name"),
    )

def get_toolkit():
    return DeltaLakeToolkit.toolkit_config_schema()

def get_tools(tool):
    return _get_toolkit(tool).get_tools()

class DeltaLakeToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    api_wrapper: Optional[DeltaLakeApiWrapper] = Field(default_factory=DeltaLakeApiWrapper.model_construct)
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

    def toolkit_config_schema() -> Type[BaseModel]:
        return DeltaLakeToolkitConfig
        return m

    @classmethod
    def get_toolkit(
        cls,
        selected_tools: list[str] | None = None,
        toolkit_name: Optional[str] = None,
        **kwargs,
    ) -> "DeltaLakeToolkit":
        delta_lake_api_wrapper = DeltaLakeApiWrapper(**kwargs)
        instance = cls(
            tools=[], api_wrapper=delta_lake_api_wrapper, toolkit_name=toolkit_name
        )
        if selected_tools:
            selected_tools = set(selected_tools)
            for t in instance.available_tools:
                if t["name"] in selected_tools:
                    instance.tools.append(
                        DeltaLakeAction(
                            api_wrapper=instance.api_wrapper,
                            name=instance.tool_prefix + t["name"],
                            description=f"S3 Path: {getattr(instance.api_wrapper, 's3_path', '')} Table Path: {getattr(instance.api_wrapper, 'table_path', '')}\n" + t["description"],
                            args_schema=t["args_schema"],
                        )
                    )
        return instance

    def get_tools(self):
        return self.tools