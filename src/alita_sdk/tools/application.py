import json
from typing import Any, Type, Optional

from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from pydantic import create_model, field_validator, BaseModel
from pydantic.fields import FieldInfo

from ..langchain.mixedAgentRenderes import convert_message_to_json
from logging import getLogger
from ..utils.utils import clean_string
logger = getLogger(__name__)

applicationToolSchema = create_model(
    "applicationSchema",
    task = (str, FieldInfo(description="Task for Application")), 
    chat_history = (str, FieldInfo(description="Chat History relevant for Application"))
)

applicationWFSchema = create_model(
    "workflowApplicationSchema",
    passed_state = (dict, FieldInfo(description="Passed State", default={})),
    messages = (list, FieldInfo(description="conversation", default=[]))
)

def formulate_query(args, kwargs):
    if kwargs.get('messages'):
        if isinstance(kwargs.get('messages')[-1], BaseMessage):
            task = kwargs.get('messages')[-1].content
            chat_history = convert_message_to_json(kwargs.get('messages')[:-1])
        elif isinstance(kwargs.get('messages')[-1], dict):
            task = kwargs.get('messages')[-1]['content']
            chat_history = kwargs.get('messages')[:-1]
        elif isinstance(kwargs.get('messages')[-1], str):
            task = kwargs.get('messages')[-1]
            chat_history = []
            for each in kwargs.get('messages')[:-1]:
                chat_history.append(AIMessage(each))
        return {"input": task, "chat_history": chat_history}
    elif kwargs.get('task'):
        task = kwargs.get('task')
        chat_history = kwargs.get('chat_history', '')        
        if chat_history:
            task = "Task: " + task + "\nAdditional context: " + chat_history
        return {"input": task, "chat_history": []}
    # else:
    #     chat_history = kwargs.get('chat_history', '')
    #     return {"input": args[0], "chat_history": chat_history}



class Application(BaseTool):
    name: str
    description: str
    application: Any
    args_schema: Type[BaseModel] = applicationToolSchema
    return_type: str = "str"
    input_variables: Optional[list[str]] = None
    output_variables: Optional[list[str]] = None
    current_state: Optional[dict] = None

    @field_validator('name', mode='before')
    @classmethod
    def remove_spaces(cls, v):
        return clean_string(v)
        
    
    def _run(self, *args, **kwargs):
        if kwargs.get('passed_state'):
            response = self.application.invoke({'input': json.dumps({var: self.current_state[var] for var in self.input_variables}), 'chat_history': []})
        else:
            response = self.application.invoke(formulate_query(args, kwargs))
        if self.return_type == "str" or self.current_state:
            return response["output"]
        elif kwargs.get("messages"):
            return {"messages": [{"role": "assistant", "content": response["output"]}]}
