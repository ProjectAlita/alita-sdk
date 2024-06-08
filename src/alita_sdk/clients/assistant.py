
from typing import Dict, Any, Optional
from langchain.agents import AgentExecutor
from langchain_core.messages import (
    BaseMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from ..agents.alita_openai import AlitaDialOpenAIAssistantRunnable
from ..agents.alita_agent import AlitaAssistantRunnable
from ..agents import create_mixed_agent


class Assistant:
    def __init__(self, client: Any, prompt: ChatPromptTemplate, tools: list,
                 openai_tools: Optional[Dict] = None):
        self.prompt = prompt
        self.client = client
        self.tools = tools
        self.openai_tools = openai_tools

    def getAgentExecutor(self):
        agent = create_mixed_agent(llm=self.client, tools=self.tools, prompt=self.prompt)
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True,
                                                  max_execution_time=None, return_intermediate_steps=True)

    def getDialOpenAIAgentExecutor(self):
        agent = AlitaDialOpenAIAssistantRunnable(client=self.client, assistant=self, 
                                             chat_history=self.prompt.messages)
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  prompt=self.prompt, verbose=True, 
                                                  handle_parsing_errors=True,
                                                  max_execution_time=None,
                                                  return_intermediate_steps=True)
    
    def getAlitaExecutor(self):
        agent = AlitaAssistantRunnable().create_assistant(
            client=self.client, tools=self.tools, prompt=self.prompt,
        )
        return AgentExecutor.from_agent_and_tools(agent=agent, tools=self.tools,
                                                  verbose=True, handle_parsing_errors=True,
                                                  max_execution_time=None,
                                                  return_intermediate_steps=True)

    # This one is used only in Alita and OpenAI
    def apredict(self, messages: list[BaseMessage]):
        yield from self.client.ainvoke(messages, functions=self.openai_tools)

    def predict(self, messages: list[BaseMessage]):
        response = self.client.invoke(messages, functions=self.openai_tools)
        return response
