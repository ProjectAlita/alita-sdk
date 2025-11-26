import logging
from traceback import format_exc
from typing import Any, Optional, List, Union

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from pydantic import Field

from ..langchain.constants import ELITEA_RS
from ..langchain.utils import create_pydantic_model, propagate_the_input_mapping

logger = logging.getLogger(__name__)

class LLMNode(BaseTool):
    """Enhanced LLM node with chat history and tool binding support"""
    
    # Override BaseTool required fields
    name: str = Field(default='LLMNode', description='Name of the LLM node')
    description: str = Field(default='This is tool node for LLM with chat history and tool support',
                             description='Description of the LLM node')

    # LLM-specific fields
    client: Any = Field(default=None, description='LLM client instance')
    return_type: str = Field(default="str", description='Return type')
    response_key: str = Field(default="messages", description='Response key')
    structured_output_dict: Optional[dict[str, str]] = Field(default=None, description='Structured output dictionary')
    output_variables: Optional[List[str]] = Field(default=None, description='Output variables')
    input_mapping: Optional[dict[str, dict]] = Field(default=None, description='Input mapping')
    input_variables: Optional[List[str]] = Field(default=None, description='Input variables')
    structured_output: Optional[bool] = Field(default=False, description='Whether to use structured output')
    available_tools: Optional[List[BaseTool]] = Field(default=None, description='Available tools for binding')
    tool_names: Optional[List[str]] = Field(default=None, description='Specific tool names to filter')
    steps_limit: Optional[int] = Field(default=25, description='Maximum steps for tool execution')

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

        func_args = propagate_the_input_mapping(input_mapping=self.input_mapping, input_variables=self.input_variables,
                                                state=state)

        # there are 2 possible flows here: LLM node from pipeline (with prompt and task)
        # or standalone LLM node for chat (with messages only)
        if 'system' in func_args.keys():
            # Flow for LLM node with prompt/task from pipeline
            if not func_args.get('system') or not func_args.get('task'):
                raise ToolException(f"LLMNode requires 'system' and 'task' parameters in input mapping. "
                                    f"Actual params: {func_args}")
            # cast to str in case user passes variable different from str
            messages = [SystemMessage(content=str(func_args.get('system'))), *func_args.get('chat_history', []), HumanMessage(content=str(func_args.get('task')))]
            # Remove pre-last item if last two messages are same type and content
            if len(messages) >= 2 and type(messages[-1]) == type(messages[-2]) and messages[-1].content == messages[
                -2].content:
                messages.pop(-2)
        else:
            # Flow for chat-based LLM node w/o prompt/task from pipeline but with messages in state
            # verify messages structure
            messages = state.get("messages", []) if isinstance(state, dict) else []
            if messages:
                # the last message has to be HumanMessage
                if not isinstance(messages[-1], HumanMessage):
                    raise ToolException("LLMNode requires the last message to be a HumanMessage")
            else:
                raise ToolException("LLMNode requires 'messages' in state for chat-based interaction")

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
                # Add default output field for proper response to user
                struct_params['elitea_response'] = {'description': 'final output to user', 'type': 'str'}
                struct_model = create_pydantic_model(f"LLMOutput", struct_params)
                completion = llm_client.invoke(messages, config=config)
                if hasattr(completion, 'tool_calls') and completion.tool_calls:
                    new_messages, _ = self.__perform_tool_calling(completion, messages, llm_client, config)
                    llm = self.__get_struct_output_model(llm_client, struct_model)
                    completion = llm.invoke(new_messages, config=config)
                    result = completion.model_dump()
                else:
                    llm = self.__get_struct_output_model(llm_client, struct_model)
                    completion = llm.invoke(messages, config=config)
                    result = completion.model_dump()

                # Ensure messages are properly formatted
                if result.get('messages') and isinstance(result['messages'], list):
                    result['messages'] = [{'role': 'assistant', 'content': '\n'.join(result['messages'])}]
                else:
                    result['messages'] = messages + [AIMessage(content=result.get(ELITEA_RS, ''))]

                return result
            else:
                # Handle regular completion
                completion = llm_client.invoke(messages, config=config)
                logger.info(f"Initial completion: {completion}")
                # Handle both tool-calling and regular responses
                if hasattr(completion, 'tool_calls') and completion.tool_calls:
                    # Handle iterative tool-calling and execution
                    new_messages, current_completion = self.__perform_tool_calling(completion, messages, llm_client, config)

                    output_msgs = {"messages": new_messages}
                    if self.output_variables:
                        if self.output_variables[0] == 'messages':
                            return output_msgs
                        output_msgs[self.output_variables[0]] = current_completion.content if current_completion else None

                    return output_msgs
                else:
                    # Regular text response
                    content = completion.content.strip() if hasattr(completion, 'content') else str(completion)

                    # Try to extract JSON if output variables are specified (but exclude 'messages' which is handled separately)
                    json_output_vars = [var for var in (self.output_variables or []) if var != 'messages']
                    if json_output_vars:
                        # set response to be the first output variable for non-structured output
                        response_data = {json_output_vars[0]: content}
                        new_messages = messages + [AIMessage(content=content)]
                        response_data['messages'] = new_messages
                        return response_data

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

    def __perform_tool_calling(self, completion, messages, llm_client, config):
        # Handle iterative tool-calling and execution
        new_messages = messages + [completion]
        iteration = 0

        # Continue executing tools until no more tool calls or max iterations reached
        current_completion = completion
        while (hasattr(current_completion, 'tool_calls') and
               current_completion.tool_calls and
               iteration < self.steps_limit):

            iteration += 1
            logger.info(f"Tool execution iteration {iteration}/{self.steps_limit}")

            # Execute each tool call in the current completion
            tool_calls = current_completion.tool_calls if hasattr(current_completion.tool_calls,
                                                                  '__iter__') else []

            for tool_call in tool_calls:
                tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call,
                                                                                                  'name',
                                                                                                  '')
                tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call,
                                                                                                  'args',
                                                                                                  {})
                tool_call_id = tool_call.get('id', '') if isinstance(tool_call, dict) else getattr(
                    tool_call, 'id', '')

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
                        # Pass the underlying config to the tool execution invoke method
                        # since it may be another agent, graph, etc. to see it properly in thinking steps
                        tool_result = tool_to_execute.invoke(tool_args, config=config)

                        # Create tool message with result - preserve structured content
                        from langchain_core.messages import ToolMessage

                        # Check if tool_result is structured content (list of dicts)
                        # TODO: need solid check for being compatible with ToolMessage content format
                        if isinstance(tool_result, list) and all(
                                isinstance(item, dict) and 'type' in item for item in tool_result
                        ):
                            # Use structured content directly for multimodal support
                            tool_message = ToolMessage(
                                content=tool_result,
                                tool_call_id=tool_call_id
                            )
                        else:
                            # Fallback to string conversion for other tool results
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
        if iteration >= self.steps_limit:
            logger.warning(f"Reached maximum iterations ({self.steps_limit}) for tool execution")
            # Add a warning message to the chat
            warning_msg = f"Maximum tool execution iterations ({self.steps_limit}) reached. Stopping tool execution."
            new_messages.append(AIMessage(content=warning_msg))
        else:
            logger.info(f"Tool execution completed after {iteration} iterations")

        return new_messages, current_completion

    def __get_struct_output_model(self, llm_client, pydantic_model):
        return llm_client.with_structured_output(pydantic_model)
