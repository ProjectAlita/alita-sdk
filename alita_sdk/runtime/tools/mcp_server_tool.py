import uuid
from logging import getLogger
from typing import Any, Type, Literal, Optional, Union, List

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model, EmailStr, constr

from ...tools.utils import TOOLKIT_SPLITTER

logger = getLogger(__name__)


class McpServerTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    return_type: str = "str"
    client: Any
    server: str
    tool_timeout_sec: int = 60


    @staticmethod
    def create_pydantic_model_from_schema(schema: dict, model_name: str = "ArgsSchema"):
        def parse_type(field: dict, name: str = "Field") -> Any:
            if "allOf" in field:
                merged = {}
                required = set()
                for idx, subschema in enumerate(field["allOf"]):
                    sub_type = parse_type(subschema, f"{name}AllOf{idx}")
                    if hasattr(sub_type, "__fields__"):
                        merged.update({k: (v.outer_type_, v.default) for k, v in sub_type.__fields__.items()})
                        required.update({k for k, v in sub_type.__fields__.items() if v.required})
                if merged:
                    return create_model(f"{name}AllOf", **merged)
                return Any
            if "anyOf" in field or "oneOf" in field:
                key = "anyOf" if "anyOf" in field else "oneOf"
                types = [parse_type(sub, f"{name}{key.capitalize()}{i}") for i, sub in enumerate(field[key])]
                # Check for null type
                if any(sub.get("type") == "null" for sub in field[key]):
                    non_null_types = [parse_type(sub, f"{name}{key.capitalize()}{i}")
                                      for i, sub in enumerate(field[key]) if sub.get("type") != "null"]
                    if len(non_null_types) == 1:
                        return Optional[non_null_types[0]]
                return Union[tuple(types)]
            t = field.get("type")
            if isinstance(t, list):
                if "null" in t:
                    non_null = [x for x in t if x != "null"]
                    if len(non_null) == 1:
                        field = dict(field)
                        field["type"] = non_null[0]
                        return Optional[parse_type(field, name)]
                    return Any
                return Any
            if t == "string":
                if "enum" in field:
                    return Literal[tuple(field["enum"])]
                if field.get("format") == "email":
                    return EmailStr
                if "pattern" in field:
                    return constr(regex=field["pattern"])
                return str
            if t == "integer":
                return int
            if t == "number":
                return float
            if t == "boolean":
                return bool
            if t == "object":
                return McpServerTool.create_pydantic_model_from_schema(field, name.capitalize())
            if t == "array":
                items = field.get("items", {})
                return List[parse_type(items, name + "Item")]
            return Any

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}
        for name, prop in properties.items():
            typ = parse_type(prop, name.capitalize())
            default = prop.get("default", ... if name in required else None)
            field_args = {}
            if "description" in prop:
                field_args["description"] = prop["description"]
            if "format" in prop:
                field_args["format"] = prop["format"]
            fields[name] = (typ, Field(default, **field_args))
        return create_model(model_name, **fields)

    def _run(self, *args, **kwargs):
        call_data = {
            "server": self.server,
            "tool_timeout_sec": self.tool_timeout_sec,
            "tool_call_id": str(uuid.uuid4()),
            "params": {
                "name": self.name.rsplit(TOOLKIT_SPLITTER)[1] if TOOLKIT_SPLITTER in self.name else self.name,
                "arguments": kwargs
            }
        }
        
        return self.client.mcp_tool_call(call_data)
