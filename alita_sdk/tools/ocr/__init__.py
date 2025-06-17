from typing import List, Literal, Optional

from langchain_core.tools import BaseToolkit, BaseTool
from pydantic import create_model, BaseModel, ConfigDict, Field

from .api_wrapper import OCRApiWrapper
from ..base.tool import BaseAction
from ..utils import clean_string, TOOLKIT_SPLITTER, get_max_toolkit_length

name = "ocr"

def get_tools(tool):
    return OCRToolkit().get_toolkit(
        selected_tools=tool['settings'].get('selected_tools', []),
        llm=tool['settings'].get('llm', None),
        alita=tool['settings'].get('alita', None),
        artifacts_folder=tool['settings'].get('artifacts_folder', ''),
        tesseract_settings=tool['settings'].get('tesseract_settings', {}),
        structured_output=tool['settings'].get('structured_output', False),
        expected_fields=tool['settings'].get('expected_fields', {}),
        toolkit_name=tool.get('toolkit_name')
    ).get_tools()

class OCRToolkit(BaseToolkit):
    tools: list[BaseTool] = []
    toolkit_max_length: int = 0

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        selected_tools = {x['name']: x['args_schema'].schema() for x in OCRApiWrapper.model_construct().get_available_tools()}
        OCRToolkit.toolkit_max_length = get_max_toolkit_length(selected_tools)
        return create_model(
            name,
            artifacts_folder=(str, Field(description="Folder path containing artifacts to process", json_schema_extra={'toolkit_name': True, 'max_toolkit_length': OCRToolkit.toolkit_max_length})),
            tesseract_settings=(dict, Field(description="Settings for Tesseract OCR processing", default={})),
            structured_output=(bool, Field(description="Whether to return structured JSON output", default=False)),
            expected_fields=(dict, Field(description="Expected fields for structured output", default={})),
            selected_tools=(List[Literal[tuple(selected_tools)]], Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={'metadata': {"label": "OCR", "icon_url": None, "hidden": True}})
        )

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, toolkit_name: Optional[str] = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        ocr_api_wrapper = OCRApiWrapper(**kwargs)
        prefix = clean_string(toolkit_name, cls.toolkit_max_length) + TOOLKIT_SPLITTER if toolkit_name else ''
        available_tools = ocr_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools and tool["name"] not in selected_tools:
                continue
            tools.append(BaseAction(
                api_wrapper=ocr_api_wrapper,
                name=prefix + tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self) -> list[BaseTool]:
        return self.tools