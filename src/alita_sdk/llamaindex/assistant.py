from llama_index.core import PromptTemplate
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.tools import BaseTool, FunctionTool
from typing import Any, Optional, Union

from ..langchain.chat_message_template import Jinja2TemplatedChatMessagesTemplate
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage
)
from ..toolkits.tools import get_tools


class ReActOverwrite(ReActAgent):
    def invoke(self, input: Union[dict[str, Any], Any], *args, **kwargs):
        output = self.chat(input['input'])
        return { "output": output, "thread_id": None }

class Assistant:
    def __init__(self, 
                 data: dict, 
                 alita_client: 'AlitaClient', 
                 chat_history: list = [], 
                 app_type: str = "llama", 
                 tools: Optional[list] = [],
                 memory: Optional[dict] = {}):    
        self.client = alita_client
        # Get Model
        integration_details = data['llm_settings']['integration_details']
        from llama_index.llms.azure_openai import AzureOpenAI
        self.llm = AzureOpenAI(
            engine=data['llm_settings']['model_name'],
            model=data['llm_settings']['model_name'],
            api_key=integration_details['settings']['api_token'] if isinstance(integration_details['settings']['api_token'], str) else integration_details['settings']['api_token']['value'],
            azure_endpoint=integration_details['settings']['api_base'],
            api_version=integration_details['settings']['api_version'],
            temperature=data['llm_settings']['temperature'],
            max_tokens=data['llm_settings']['max_tokens'],
        )
        # Reconstruct chat history
        self.prompt = PromptTemplate(self.prepare_prompt_template(data['instructions'], data['variables']))
        self.chat_history = [ChatMessage(content=self.prompt, role=MessageRole.SYSTEM)]
        for message in chat_history:
            self.chat_history.append(ChatMessage(content=message.content, role=MessageRole.USER if message.role == "user" else MessageRole.ASSISTANT))
        # Transform tools
        self.tools = self.transform_tools(data['tools'])

    def reActAgent(self):
        return ReActOverwrite.from_tools(self.tools, llm=self.llm, chat_history=self.chat_history, verbose=True)    
    
    def transform_tools(self, tools: list[dict]):
        lch_tools = get_tools(tools, self.client)
        llama_tools = []
        for tool in lch_tools:
            llama_tools.append(FunctionTool.from_defaults(fn=tool._run, name=tool.name, description=tool.description, fn_schema=tool.args_schema))
        return llama_tools
        
    def prepare_prompt_template(self, context: str, variables: list[dict]):
        # Extracting variables, as llama need  single mustache variables, and we have double mustache variables
        variables = {}
        input_variables = []
        for variable in variables:
            if variable['value'] != "":
                variables[variable['name']] = variable['value']
            else:
                input_variables.append(variable['name'])
        template = Jinja2TemplatedChatMessagesTemplate(messages=[SystemMessage(content=context)])
        return template.format_messages(**variables)[0].content
