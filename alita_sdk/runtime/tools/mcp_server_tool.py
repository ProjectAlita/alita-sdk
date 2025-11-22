import uuid
from logging import getLogger
from typing import Any, Type, Literal, Optional, Union, List

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model, EmailStr, constr, ConfigDict

from ...tools.utils import TOOLKIT_SPLITTER

logger = getLogger(__name__)


class McpServerTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    return_type: str = "str"
    client: Any = Field(default=None, exclude=True)  # Exclude from serialization
    server: str
    tool_timeout_sec: int = 60

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __getstate__(self):
        """Custom serialization to exclude non-serializable objects."""
        state = self.__dict__.copy()
        # Remove the client since it contains threading objects that can't be pickled
        state['client'] = None
        # Store args_schema as a schema dict instead of the dynamic class
        if hasattr(self, 'args_schema') and self.args_schema is not None:
            # Convert the Pydantic model back to schema dict for pickling
            try:
                state['_args_schema_dict'] = self.args_schema.model_json_schema()
                state['args_schema'] = None
            except Exception as e:
                logger.warning(f"Failed to serialize args_schema: {e}")
                # If conversion fails, just remove it
                state['args_schema'] = None
                state['_args_schema_dict'] = {}
        return state

    def __setstate__(self, state):
        """Custom deserialization to handle missing objects."""
        # Restore the args_schema from the stored schema dict
        args_schema_dict = state.pop('_args_schema_dict', {})

        # Initialize required Pydantic internal attributes
        if '__pydantic_fields_set__' not in state:
            state['__pydantic_fields_set__'] = set(state.keys())
        if '__pydantic_extra__' not in state:
            state['__pydantic_extra__'] = None
        if '__pydantic_private__' not in state:
            state['__pydantic_private__'] = None

        # Directly update the object's __dict__ to bypass Pydantic validation
        self.__dict__.update(state)

        # Recreate the args_schema from the stored dict if available
        if args_schema_dict:
            try:
                recreated_schema = self.create_pydantic_model_from_schema(args_schema_dict)
                self.__dict__['args_schema'] = recreated_schema
            except Exception as e:
                logger.warning(f"Failed to recreate args_schema: {e}")
                self.__dict__['args_schema'] = None
        else:
            self.__dict__['args_schema'] = None

        # Note: client will be None after unpickling
        # The toolkit should reinitialize the client when needed


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
