import json

from ..utils.utils import clean_string
from langchain_core.tools import BaseTool, ToolException
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from typing import Any, Type, Optional
from pydantic import create_model, field_validator, BaseModel
from pydantic.fields import FieldInfo
from ..langchain.mixedAgentRenderes import convert_message_to_json
from logging import getLogger
logger = getLogger(__name__)

applicationToolSchema = create_model(
    "applicatrionSchema", 
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (Optional[list[BaseMessage]], FieldInfo(description="Chat History relevant for Application", default=[]))
)

def formulate_query(kwargs):
    chat_history = []
    if kwargs.get('chat_history'):
        if isinstance(kwargs.get('chat_history')[-1], BaseMessage):
            chat_history = convert_message_to_json(kwargs.get('chat_history')[:])
        elif isinstance(kwargs.get('chat_history')[-1], dict):
            if all([True if message.get('role') and message.get('content') else False for message in kwargs.get('chat_history')]):
                chat_history = kwargs.get('chat_history')[:]
            else:
                for each in kwargs.get('chat_history')[:]:
                    chat_history.append(AIMessage(json.dumps(each)))
        elif isinstance(kwargs.get('chat_history')[-1], str):
            chat_history = []
            for each in kwargs.get('chat_history')[:]:
                chat_history.append(AIMessage(each))
    user_task = kwargs.get('task')
    if not user_task:
        raise ToolException("Task is required to invoke the application. "
                            "Check the provided input (some errors may happen on previous steps).")
    input_message = HumanMessage(content=user_task)
    result = {"input": [input_message], "chat_history": chat_history}
    for key, value in kwargs.items():
        if key not in ("task", "chat_history"):
            result[key] = value
    return result
    
    

class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    client: Any
    args_runnable: dict = {}
    
    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)

    def invoke(self, input: Any, config: Optional[dict] = None, **kwargs: Any) -> Any:
        """Override default invoke to preserve all fields, not just args_schema"""
        schema_values = self.args_schema(**input).model_dump() if self.args_schema else {}
        extras = {k: v for k, v in input.items() if k not in schema_values}
        all_kwargs = {**kwargs, **extras, **schema_values}
        if config is None:
            config = {}
        return self._run(*config, **all_kwargs)

    def _run(self, *args, **kwargs):
        if self.client and self.args_runnable:
            # Recreate new LanggraphAgentRunnable in order to reflect the current input_mapping (it can be dynamic for pipelines).
            # Actually, for pipelines agent toolkits LanggraphAgentRunnable is created (for LLMNode) before pipeline's schema parsing.
            application_variables = {k: {"name": k, "value": v} for k, v in kwargs.items()}
            self.application = self.client.application(**self.args_runnable, application_variables=application_variables)
        response = self.application.invoke(formulate_query(kwargs))
        if self.return_type == "str":
            return response["output"]
        else:
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
    
