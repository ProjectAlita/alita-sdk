from typing import Dict, List, Literal, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, ConfigDict, Field, create_model

from ..base.tool import BaseAction
from .api_wrapper import (
    FigmaApiWrapper,
    GLOBAL_LIMIT,
    DEFAULT_FIGMA_IMAGES_PROMPT,
    DEFAULT_FIGMA_SUMMARY_PROMPT,
    DEFAULT_NUMBER_OF_THREADS,
)
from ..elitea_base import filter_missconfigured_index_tools
from ...configurations.figma import FigmaConfiguration
from ...configurations.pgvector import PgVectorConfiguration
from ...runtime.utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

name = "figma"

def get_tools(tool):
    return (
        FigmaToolkit()
        .get_toolkit(
            selected_tools=tool["settings"].get("selected_tools", []),
            figma_configuration=tool['settings']['figma_configuration'],
            global_limit=tool["settings"].get("global_limit", GLOBAL_LIMIT),
            global_regexp=tool["settings"].get("global_regexp", None),
            toolkit_name=tool.get('toolkit_name'),
            # indexer settings
            llm=tool['settings'].get('llm', None),
            alita=tool['settings'].get('alita', None),
            pgvector_configuration=tool['settings'].get('pgvector_configuration', {}),
            collection_name=str(tool['toolkit_name']),
            doctype='doc',
            embedding_model=tool['settings'].get('embedding_model'),
            vectorstore_type="PGVector",
            # figma summary/image prompt settings (toolkit-level)
            # TODO disabled until new requirements
            # apply_images_prompt=tool["settings"].get("apply_images_prompt"),
            # images_prompt=tool["settings"].get("images_prompt"),
            # apply_summary_prompt=tool["settings"].get("apply_summary_prompt"),
            # summary_prompt=tool["settings"].get("summary_prompt"),
            # number_of_threads=tool["settings"].get("number_of_threads"),
        )
        .get_tools()
    )


class FigmaToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {
            x["name"]: x["args_schema"].schema()
            for x in FigmaApiWrapper.model_construct().get_available_tools()
        }
        return create_model(
            name,
            # TODO disabled until new requirements
            # apply_images_prompt=(Optional[bool], Field(
            #     description="Enable advanced image processing instructions for Figma image nodes.",
            #     default=True,
            # )),
            # images_prompt=(Optional[Dict[str, str]], Field(
            #     description=(
            #         "Instruction for how to analyze image-based nodes "
            #         "(screenshots, diagrams, etc.) during Figma file retrieving. "
            #         "Must contain a single 'prompt' key with the text."
            #     ),
            #     default=DEFAULT_FIGMA_IMAGES_PROMPT,
            # )),
            # apply_summary_prompt=(Optional[bool], Field(
            #     description="Enable LLM-based summarization over loaded Figma data.",
            #     default=True,
            # )),
            # summary_prompt=(Optional[Dict[str, str]], Field(
            #     description=(
            #         "Instruction for the LLM on how to summarize loaded Figma data. "
            #         "Must contain a single 'prompt' key with the text."
            #     ),
            #     default=DEFAULT_FIGMA_SUMMARY_PROMPT,
            # )),
            number_of_threads=(Optional[int], Field(
                description=(
                    "Number of worker threads to use when downloading and processing Figma images. "
                    f"Valid values are from 1 to 5. Default is {DEFAULT_NUMBER_OF_THREADS}."
                ),
                default=DEFAULT_NUMBER_OF_THREADS,
                ge=1,
                le=5,
            )),
            global_limit=(Optional[int], Field(description="Global limit", default=GLOBAL_LIMIT)),
            global_regexp=(Optional[str], Field(description="Global regex pattern", default=None)),
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(default=[], json_schema_extra={"args_schemas": selected_tools}),
            ),
            # Figma configuration
            figma_configuration=(FigmaConfiguration, Field(description="Figma configuration", json_schema_extra={'configuration_types': ['figma']})),

            # indexer settings
            pgvector_configuration=(Optional[PgVectorConfiguration], Field(description="PgVector Configuration", json_schema_extra={'configuration_types': ['pgvector']})),

            # embedder settings
            embedding_model=(Optional[str], Field(default=None, description="Embedding configuration.", json_schema_extra={'configuration_model': 'embedding'})),
            __config__=ConfigDict(
                json_schema_extra={
                     "metadata": {
                         "label": "Figma",
                         "icon_url": "figma-icon.svg",
                         "categories": ["other"],
                         "extra_categories": ["figma", "design", "ui/ux", "prototyping", "collaboration"],
                     }
                 }
            ),
        )

    @classmethod
    @filter_missconfigured_index_tools
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        wrapper_payload = {
            **kwargs,
            **kwargs.get('figma_configuration'),
            **(kwargs.get('pgvector_configuration') or {}),
        }
        figma_api_wrapper = FigmaApiWrapper(**wrapper_payload)
        available_tools = figma_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            description = tool["description"]
            if toolkit_name:
                description = f"Toolkit: {toolkit_name}\n{description}"
            description = description[:1000]
            tools.append(
                BaseAction(
                    api_wrapper=figma_api_wrapper,
                    name=tool["name"],
                    description=description,
                    args_schema=tool["args_schema"],
                    metadata={TOOLKIT_NAME_META: toolkit_name, TOOLKIT_TYPE_META: name, TOOL_NAME_META: tool["name"]} if toolkit_name else {TOOL_NAME_META: tool["name"]}
                )
            )
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
