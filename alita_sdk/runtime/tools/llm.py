import json
import logging
from traceback import format_exc
from typing import Any, Optional, Dict, List, Union

from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool, ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import Field

from ..langchain.utils import _extract_json, create_pydantic_model, create_params

logger = logging.getLogger(__name__)


def create_llm_input_with_messages(
    prompt: Dict[str, str], 
    messages: List[BaseMessage], 
    params: Dict[str, Any]
) -> List[BaseMessage]:
    """
    Create LLM input by combining system prompt with chat history messages.
    
    Args:
        prompt: The prompt configuration with template
        messages: List of chat history messages
        params: Additional parameters for prompt formatting
        
    Returns:
        List of messages to send to LLM
    """
    logger.info(f"Creating LLM input with messages: {len(messages)} messages, params: {params}")
    
    # Build the input messages
    input_messages = []
    
    # Add system message from prompt if available
    if prompt:
        try:
            # Format the system message using the prompt template or value and params
            prompt_str = prompt['template'] if 'template' in prompt else prompt['value']
            system_content = prompt_str.format(**params) if params else prompt_str
            input_messages.append(SystemMessage(content=system_content))
        except KeyError as e:
            error_msg = f"KeyError in prompt formatting: {e}. Available params: {list(params.keys())}"
            logger.error(error_msg)
            raise ToolException(error_msg)
    
    # Add the chat history messages
    if messages:
        input_messages.extend(messages)
    
    return input_messages


class LLMNode(BaseTool):
    """Enhanced LLM node with chat history and tool binding support"""
    
    # Override BaseTool required fields
    name: str = Field(default='LLMNode', description='Name of the LLM node')
    description: str = Field(default='This is tool node for LLM with chat history and tool support', description='Description of the LLM node')
    
    # LLM-specific fields
    prompt: Dict[str, str] = Field(default_factory=dict, description='Prompt configuration')
    client: Any = Field(default=None, description='LLM client instance')
    return_type: str = Field(default="str", description='Return type')
    response_key: str = Field(default="messages", description='Response key')
    structured_output_dict: Optional[dict[str, str]] = Field(default=None, description='Structured output dictionary')
    output_variables: Optional[List[str]] = Field(default=None, description='Output variables')
    input_variables: Optional[List[str]] = Field(default=None, description='Input variables')
    structured_output: Optional[bool] = Field(default=False, description='Whether to use structured output')
    available_tools: Optional[List[BaseTool]] = Field(default=None, description='Available tools for binding')
    tool_names: Optional[List[str]] = Field(default=None, description='Specific tool names to filter')

    def get_filtered_tools(self) -> List[BaseTool]:
        """
        Filter available tools based on tool_names list.
        
        Returns:
            List of filtered tools
        """
        if not self.available_tools:
            return []
            
        if not self.tool_names:
            # If no specific tool names provided, return all available tools
            return self.available_tools
            
        # Filter tools by name
        filtered_tools = []
        available_tool_names = {tool.name: tool for tool in self.available_tools}
        
        for tool_name in self.tool_names:
            if tool_name in available_tool_names:
                filtered_tools.append(available_tool_names[tool_name])
                logger.debug(f"Added tool '{tool_name}' to LLM node")
            else:
                logger.warning(f"Tool '{tool_name}' not found in available tools: {list(available_tool_names.keys())}")
        
        return filtered_tools

    def invoke(
        self,
        state: Union[str, dict],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> dict:
        """
        Invoke the LLM node with proper message handling and tool binding.
        
        Args:
            state: The current state containing messages and other variables
            config: Optional runnable config
            **kwargs: Additional keyword arguments
            
        Returns:
            Updated state with LLM response
        """
        # Extract messages from state
        
        messages = state.get("messages", []) if isinstance(state, dict) else []
        logger.info(f"Invoking LLMNode with {len(messages)} messages")
        logger.info("Messages: %s", messages)
        # Create parameters for prompt formatting from state
        params = {}
        if isinstance(state, dict):
            for var in self.input_variables or []:
                if var != "messages" and var in state:
                    params[var] = state[var]
        
        # Create LLM input with proper message handling
        llm_input = create_llm_input_with_messages(self.prompt, messages, params)
        
        # Get the LLM client, potentially with tools bound
        llm_client = self.client
        
        if len(self.tool_names or []) > 0:
            filtered_tools = self.get_filtered_tools()
            if filtered_tools:
                logger.info(f"Binding {len(filtered_tools)} tools to LLM: {[t.name for t in filtered_tools]}")
                llm_client = self.client.bind_tools(filtered_tools)
            else:
                logger.warning("No tools to bind to LLM")
        
        try:
            if self.structured_output and self.output_variables:
                # Handle structured output
                struct_params = {
                    key: {
                        "type": 'list[str]' if 'list' in value else value,
                        "description": ""
                    }
                    for key, value in (self.structured_output_dict or {}).items()
                }
                struct_model = create_pydantic_model(f"LLMOutput", struct_params)
                llm = llm_client.with_structured_output(struct_model)
                completion = llm.invoke(llm_input, config=config)
                result = completion.model_dump()
                
                # Ensure messages are properly formatted
                if result.get('messages') and isinstance(result['messages'], list):
                    result['messages'] = [{'role': 'assistant', 'content': '\n'.join(result['messages'])}]
                
                return result
            else:
                # Handle regular completion
                completion = llm_client.invoke(llm_input, config=config)
                logger.info(f"Initial completion: {completion}")
                # Handle both tool-calling and regular responses
                if hasattr(completion, 'tool_calls') and completion.tool_calls:
                    # Handle iterative tool-calling and execution
                    new_messages = messages + [completion]
                    max_iterations = 15
                    iteration = 0
                    
                    # Continue executing tools until no more tool calls or max iterations reached
                    current_completion = completion
                    while (hasattr(current_completion, 'tool_calls') and 
                           current_completion.tool_calls and 
                           iteration < max_iterations):
                        
                        iteration += 1
                        logger.info(f"Tool execution iteration {iteration}/{max_iterations}")
                        
                        # Execute each tool call in the current completion
                        tool_calls = current_completion.tool_calls if hasattr(current_completion.tool_calls, '__iter__') else []
                        
                        for tool_call in tool_calls:
                            tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                            tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                            tool_call_id = tool_call.get('id', '') if isinstance(tool_call, dict) else getattr(tool_call, 'id', '')
                            
                            # Find the tool in filtered tools
                            filtered_tools = self.get_filtered_tools()
                            tool_to_execute = None
                            for tool in filtered_tools:
                                if tool.name == tool_name:
                                    tool_to_execute = tool
                                    break
                            
                            if tool_to_execute:
                                try:
                                    logger.info(f"Executing tool '{tool_name}' with args: {tool_args}")
                                    tool_result = tool_to_execute.invoke(tool_args)
                                    
                                    # Create tool message with result
                                    from langchain_core.messages import ToolMessage
                                    tool_message = ToolMessage(
                                        content=str(tool_result),
                                        tool_call_id=tool_call_id
                                    )
                                    new_messages.append(tool_message)
                                    
                                except Exception as e:
                                    logger.error(f"Error executing tool '{tool_name}': {e}")
                                    # Create error tool message
                                    from langchain_core.messages import ToolMessage
                                    tool_message = ToolMessage(
                                        content=f"Error executing {tool_name}: {str(e)}",
                                        tool_call_id=tool_call_id
                                    )
                                    new_messages.append(tool_message)
                            else:
                                logger.warning(f"Tool '{tool_name}' not found in available tools")
                                # Create error tool message for missing tool
                                from langchain_core.messages import ToolMessage
                                tool_message = ToolMessage(
                                    content=f"Tool '{tool_name}' not available",
                                    tool_call_id=tool_call_id
                                )
                                new_messages.append(tool_message)
                        
                        # Call LLM again with tool results to get next response
                        try:
                            current_completion = llm_client.invoke(new_messages, config=config)
                            new_messages.append(current_completion)
                            
                            # Check if we still have tool calls
                            if hasattr(current_completion, 'tool_calls') and current_completion.tool_calls:
                                logger.info(f"LLM requested {len(current_completion.tool_calls)} more tool calls")
                            else:
                                logger.info("LLM completed without requesting more tools")
                                break
                                
                        except Exception as e:
                            logger.error(f"Error in LLM call during iteration {iteration}: {e}")
                            # Add error message and break the loop
                            error_msg = f"Error processing tool results in iteration {iteration}: {str(e)}"
                            new_messages.append(AIMessage(content=error_msg))
                            break
                    
                    # Log completion status
                    if iteration >= max_iterations:
                        logger.warning(f"Reached maximum iterations ({max_iterations}) for tool execution")
                        # Add a warning message to the chat
                        warning_msg = f"Maximum tool execution iterations ({max_iterations}) reached. Stopping tool execution."
                        new_messages.append(AIMessage(content=warning_msg))
                    else:
                        logger.info(f"Tool execution completed after {iteration} iterations")
                    
                    return {"messages": new_messages}
                else:
                    # Regular text response
                    content = completion.content.strip() if hasattr(completion, 'content') else str(completion)
                    
                    # Try to extract JSON if output variables are specified (but exclude 'messages' which is handled separately)
                    json_output_vars = [var for var in (self.output_variables or []) if var != 'messages']
                    if json_output_vars:
                        try:
                            response = _extract_json(content) or {}
                            response_data = {key: response.get(key) for key in json_output_vars if key in response}
                            
                            # Always add the messages to the response
                            new_messages = messages + [AIMessage(content=content)]
                            response_data['messages'] = new_messages
                            
                            return response_data
                        except (ValueError, json.JSONDecodeError) as e:
                            # LLM returned non-JSON content, treat as plain text
                            logger.warning(f"Expected JSON output but got plain text. Output variables specified: {json_output_vars}. Error: {e}")
                            # Fall through to plain text handling
                    
                    # Simple text response (either no output variables or JSON parsing failed)
                    new_messages = messages + [AIMessage(content=content)]
                    return {"messages": new_messages}
                        
        except Exception as e:
            logger.error(f"Error in LLM Node: {format_exc()}")
            error_msg = f"Error: {e}"
            new_messages = messages + [AIMessage(content=error_msg)]
            return {"messages": new_messages}

    def _run(self, *args, **kwargs):
        # Legacy support for old interface
        return self.invoke(kwargs, **kwargs)
