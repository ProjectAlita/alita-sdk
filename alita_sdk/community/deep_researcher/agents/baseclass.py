from typing import Any, Callable, Optional, List, Dict, Union, TypeVar, Generic, Type
from pydantic import BaseModel
import asyncio
import json

# LangChain imports
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor
from langchain_core.runnables import RunnablePassthrough
from langchain.agents.format_scratchpad import format_to_openai_functions
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.runnables.base import RunnableSerializable

# Type variable for parameterizing the output type
TContext = TypeVar("TContext")

class ResearchRunner:
    """
    LangChain-based runner for research agents that supports both structured output
    and custom output parsing.
    """
    
    @classmethod
    async def run(cls, agent, user_message: str, **kwargs) -> 'RunResult':
        """
        Run the agent with the given user message and return the result.
        
        Args:
            agent: The agent to run
            user_message: The user message to send to the agent
            
        Returns:
            A RunResult containing the final output
        """
        if not isinstance(agent, ResearchAgent):
            raise TypeError("Agent must be a ResearchAgent")
        
        result = await agent.arun(user_message)
        return RunResult(final_output=result)

class RunResult:
    """
    A simple class to maintain compatibility with the previous API
    while using LangChain agents under the hood.
    """
    
    def __init__(self, final_output: Any):
        self.final_output = final_output
    
    def final_output_as(self, output_type: Type[Any]) -> Any:
        """
        Convert the final output to the specified type.
        
        Args:
            output_type: The type to convert to
            
        Returns:
            An instance of output_type
        """
        if isinstance(self.final_output, output_type):
            return self.final_output
        
        if isinstance(self.final_output, str):
            try:
                # Try to parse as JSON if it's a string
                parsed = json.loads(self.final_output)
                return output_type(**parsed)
            except Exception:
                # If that fails, try to parse the string for JSON
                try:
                    # Look for JSON-like content in the string
                    import re
                    json_match = re.search(r'```json\n(.*?)\n```', self.final_output, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        parsed = json.loads(json_str)
                        return output_type(**parsed)
                except Exception:
                    pass
        
        # If all else fails, try to initialize with the entire output as a string
        try:
            if hasattr(output_type, "model_validate"):
                return output_type.model_validate({"output": self.final_output})
            else:
                return output_type(output=self.final_output)
        except Exception as e:
            raise ValueError(f"Could not convert output to {output_type.__name__}: {e}")

class ResearchAgent(Generic[TContext]):
    """
    LangChain-based agent for research tasks that supports both structured output
    and custom output parsing.
    """
    
    def __init__(
        self,
        name: str,
        instructions: str,
        tools: List[BaseTool],
        model: Any,
        output_type: Optional[Type[BaseModel]] = None,
        output_parser: Optional[Callable[[str], Any]] = None
    ):
        self.name = name
        self.instructions = instructions
        self.tools = tools
        self.model = model
        self.output_type = output_type
        self.output_parser = output_parser
        
        # Create the LangChain agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> RunnableSerializable:
        """
        Create a LangChain agent with the specified configuration.
        """
        # Create the system prompt
        system_prompt = self.instructions
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("ai", "{agent_scratchpad}")
        ])
        
        # Create the LangChain agent
        agent = (
            {
                "input": RunnablePassthrough(),
                "agent_scratchpad": lambda x: format_to_openai_functions(x["intermediate_steps"])
            }
            | prompt
            | self.model
            | OpenAIFunctionsAgentOutputParser()
        )
        
        # Create the agent executor
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
    
    async def arun(self, user_input: str) -> Any:
        """
        Run the agent asynchronously with the given user input.
        
        Args:
            user_input: The user input to send to the agent
            
        Returns:
            The agent's output
        """
        try:
            # Run the agent
            result = await self.agent.ainvoke({"input": user_input, "intermediate_steps": []})
            output = result.get("output", "")
            
            # Apply output parser if specified
            if self.output_parser is not None:
                return self.output_parser(output)
            
            # Try to convert to output_type if specified
            if self.output_type is not None:
                try:
                    return self.output_type.model_validate_json(output)
                except Exception:
                    try:
                        return self.output_type.model_validate({"output": output})
                    except Exception:
                        pass
            
            # Otherwise return the raw output
            return output
        except Exception as e:
            return f"Error: {str(e)}"