import asyncio
import logging
from traceback import format_exc
from typing import Any, Optional, List, Union, Literal

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
    tool_execution_timeout: Optional[int] = Field(default=900, description='Timeout (seconds) for tool execution. Default is 15 minutes.')

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

    def _get_tool_truncation_suggestions(self, tool_name: Optional[str]) -> str:
        """
        Get context-specific suggestions for how to reduce output from a tool.
        
        First checks if the tool itself provides truncation suggestions via 
        `truncation_suggestions` attribute or `get_truncation_suggestions()` method.
        Falls back to generic suggestions if the tool doesn't provide any.
        
        Args:
            tool_name: Name of the tool that caused the context overflow
            
        Returns:
            Formatted string with numbered suggestions for the specific tool
        """
        suggestions = None
        
        # Try to get suggestions from the tool itself
        if tool_name:
            filtered_tools = self.get_filtered_tools()
            for tool in filtered_tools:
                if tool.name == tool_name:
                    # Check for truncation_suggestions attribute
                    if hasattr(tool, 'truncation_suggestions') and tool.truncation_suggestions:
                        suggestions = tool.truncation_suggestions
                        break
                    # Check for get_truncation_suggestions method
                    elif hasattr(tool, 'get_truncation_suggestions') and callable(tool.get_truncation_suggestions):
                        suggestions = tool.get_truncation_suggestions()
                        break
        
        # Fall back to generic suggestions if tool doesn't provide any
        if not suggestions:
            suggestions = [
                "Check if the tool has parameters to limit output size (e.g., max_items, max_results, max_depth)",
                "Target a more specific path or query instead of broad searches",
                "Break the operation into smaller, focused requests",
            ]
        
        # Format as numbered list
        return "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions))

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
            if func_args.get('system') is None or func_args.get('task') is None:
                raise ToolException(f"LLMNode requires 'system' and 'task' parameters in input mapping. "
                                    f"Actual params: {func_args}")
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
                struct_params['elitea_response'] = {
                    'description': 'final output to user (summarized output from LLM)', 'type': 'str',
                    "default": None}
                struct_model = create_pydantic_model(f"LLMOutput", struct_params)
                initial_completion = llm_client.invoke(messages, config=config)
                if hasattr(initial_completion, 'tool_calls') and initial_completion.tool_calls:
                    new_messages, _ = self._run_async_in_sync_context(
                        self.__perform_tool_calling(initial_completion, messages, llm_client, config)
                    )
                    llm = self.__get_struct_output_model(llm_client, struct_model)
                    completion = llm.invoke(new_messages, config=config)
                    result = completion.model_dump()
                else:
                    try:
                        llm = self.__get_struct_output_model(llm_client, struct_model)
                        completion = llm.invoke(messages, config=config)
                    except ValueError as e:
                        logger.error(f"Error invoking structured output model: {format_exc()}")
                        logger.info("Attemping to fall back to json mode")
                        # Fallback to regular LLM with JSON extraction
                        completion = self.__get_struct_output_model(llm_client, struct_model,
                                                                    method="json_mode").invoke(messages, config=config)
                    result = completion.model_dump()

                # Ensure messages are properly formatted
                if result.get('messages') and isinstance(result['messages'], list):
                    result['messages'] = [{'role': 'assistant', 'content': '\n'.join(result['messages'])}]
                else:
                    result['messages'] = messages + [
                        AIMessage(content=result.get(ELITEA_RS, '') or initial_completion.content)]

                return result
            else:
                # Handle regular completion
                completion = llm_client.invoke(messages, config=config)
                logger.info(f"Initial completion: {completion}")
                # Handle both tool-calling and regular responses
                if hasattr(completion, 'tool_calls') and completion.tool_calls:
                    # Handle iterative tool-calling and execution
                    new_messages, current_completion = self._run_async_in_sync_context(
                        self.__perform_tool_calling(completion, messages, llm_client, config)
                    )

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
    
    def _run_async_in_sync_context(self, coro):
        """Run async coroutine from sync context.
        
        For MCP tools with persistent sessions, we reuse the same event loop
        that was used to create the MCP client and sessions (set by CLI).

        When called from within a running event loop (e.g., nested LLM nodes),
        we need to handle this carefully to avoid "event loop already running" errors.

        This method handles three scenarios:
        1. Called from async context (event loop running) - creates new thread with new loop
        2. Called from sync context with persistent loop - reuses persistent loop
        3. Called from sync context without loop - creates new persistent loop
        """
        import threading

        # Check if there's a running loop
        try:
            running_loop = asyncio.get_running_loop()
            loop_is_running = True
            logger.debug(f"Detected running event loop (id: {id(running_loop)}), executing tool calls in separate thread")
        except RuntimeError:
            loop_is_running = False

        # Scenario 1: Loop is currently running - MUST use thread
        if loop_is_running:
            result_container = []
            exception_container = []

            # Try to capture Streamlit context from current thread for propagation
            streamlit_ctx = None
            try:
                from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx
                streamlit_ctx = get_script_run_ctx()
                if streamlit_ctx:
                    logger.debug("Captured Streamlit context for propagation to worker thread")
            except (ImportError, Exception) as e:
                logger.debug(f"Streamlit context not available or failed to capture: {e}")

            def run_in_thread():
                """Run coroutine in a new thread with its own event loop."""
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                    result_container.append(result)
                except Exception as e:
                    logger.debug(f"Exception in async thread: {e}")
                    exception_container.append(e)
                finally:
                    new_loop.close()
                    asyncio.set_event_loop(None)

            thread = threading.Thread(target=run_in_thread, daemon=False)

            # Propagate Streamlit context to the worker thread if available
            if streamlit_ctx is not None:
                try:
                    add_script_run_ctx(thread, streamlit_ctx)
                    logger.debug("Successfully propagated Streamlit context to worker thread")
                except Exception as e:
                    logger.warning(f"Failed to propagate Streamlit context to worker thread: {e}")

            thread.start()
            thread.join(timeout=self.tool_execution_timeout)  # 15 minute timeout for safety

            if thread.is_alive():
                logger.error("Async operation timed out after 5 minutes")
                raise TimeoutError("Async operation in thread timed out")

            # Re-raise exception if one occurred
            if exception_container:
                raise exception_container[0]

            return result_container[0] if result_container else None

        # Scenario 2 & 3: No loop running - use or create persistent loop
        else:
            # Get or create persistent loop
            if not hasattr(self.__class__, '_persistent_loop') or \
               self.__class__._persistent_loop is None or \
               self.__class__._persistent_loop.is_closed():
                self.__class__._persistent_loop = asyncio.new_event_loop()
                logger.debug("Created persistent event loop for async tools")

            loop = self.__class__._persistent_loop

            # Double-check the loop is not running (safety check)
            if loop.is_running():
                logger.debug("Persistent loop is unexpectedly running, using thread execution")

                result_container = []
                exception_container = []

                # Try to capture Streamlit context from current thread for propagation
                streamlit_ctx = None
                try:
                    from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx
                    streamlit_ctx = get_script_run_ctx()
                    if streamlit_ctx:
                        logger.debug("Captured Streamlit context for propagation to worker thread")
                except (ImportError, Exception) as e:
                    logger.debug(f"Streamlit context not available or failed to capture: {e}")

                def run_in_thread():
                    """Run coroutine in a new thread with its own event loop."""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(coro)
                        result_container.append(result)
                    except Exception as ex:
                        logger.debug(f"Exception in async thread: {ex}")
                        exception_container.append(ex)
                    finally:
                        new_loop.close()
                        asyncio.set_event_loop(None)

                thread = threading.Thread(target=run_in_thread, daemon=False)

                # Propagate Streamlit context to the worker thread if available
                if streamlit_ctx is not None:
                    try:
                        add_script_run_ctx(thread, streamlit_ctx)
                        logger.debug("Successfully propagated Streamlit context to worker thread")
                    except Exception as e:
                        logger.warning(f"Failed to propagate Streamlit context to worker thread: {e}")

                thread.start()
                thread.join(timeout=self.tool_execution_timeout)

                if thread.is_alive():
                    logger.error("Async operation timed out after 15 minutes")
                    raise TimeoutError("Async operation in thread timed out")

                if exception_container:
                    raise exception_container[0]

                return result_container[0] if result_container else None
            else:
                # Loop exists but not running - safe to use run_until_complete
                logger.debug(f"Using persistent loop (id: {id(loop)}) with run_until_complete")
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)

    async def _arun(self, *args, **kwargs):
        # Legacy async support
        return self.invoke(kwargs, **kwargs)

    async def __perform_tool_calling(self, completion, messages, llm_client, config):
        # Handle iterative tool-calling and execution
        logger.info(f"__perform_tool_calling called with {len(completion.tool_calls) if hasattr(completion, 'tool_calls') else 0} tool calls")
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
                        
                        # Try async invoke first (for MCP tools), fallback to sync
                        tool_result = None
                        if hasattr(tool_to_execute, 'ainvoke'):
                            try:
                                tool_result = await tool_to_execute.ainvoke(tool_args, config=config)
                            except (NotImplementedError, AttributeError):
                                logger.debug(f"Tool '{tool_name}' ainvoke failed, falling back to sync invoke")
                                tool_result = tool_to_execute.invoke(tool_args, config=config)
                        else:
                            # Sync-only tool
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
                        import traceback
                        error_details = traceback.format_exc()
                        # Use debug level to avoid duplicate output when CLI callbacks are active
                        logger.debug(f"Error executing tool '{tool_name}': {e}\n{error_details}")
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
                error_str = str(e).lower()
                
                # Check for context window / token limit errors
                is_context_error = any(indicator in error_str for indicator in [
                    'context window', 'context_window', 'token limit', 'too long',
                    'maximum context length', 'input is too long', 'exceeds the limit',
                    'contextwindowexceedederror', 'max_tokens', 'content too large'
                ])
                
                # Check for Bedrock/Claude output limit errors
                # These often manifest as "model identifier is invalid" when output exceeds limits
                is_output_limit_error = any(indicator in error_str for indicator in [
                    'model identifier is invalid',
                    'bedrockexception',
                    'output token',
                    'response too large',
                    'max_tokens_to_sample',
                    'output_token_limit'
                ])
                
                if is_context_error or is_output_limit_error:
                    error_type = "output limit" if is_output_limit_error else "context window"
                    logger.warning(f"{error_type.title()} exceeded during tool execution iteration {iteration}")
                    
                    # Find the last tool message and its associated tool name
                    last_tool_msg_idx = None
                    last_tool_name = None
                    last_tool_call_id = None
                    
                    # First, find the last tool message
                    for i in range(len(new_messages) - 1, -1, -1):
                        msg = new_messages[i]
                        if hasattr(msg, 'tool_call_id') or (hasattr(msg, 'type') and getattr(msg, 'type', None) == 'tool'):
                            last_tool_msg_idx = i
                            last_tool_call_id = getattr(msg, 'tool_call_id', None)
                            break
                    
                    # Find the tool name from the AIMessage that requested this tool call
                    if last_tool_call_id:
                        for i in range(last_tool_msg_idx - 1, -1, -1):
                            msg = new_messages[i]
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tc_id = tc.get('id', '') if isinstance(tc, dict) else getattr(tc, 'id', '')
                                    if tc_id == last_tool_call_id:
                                        last_tool_name = tc.get('name', '') if isinstance(tc, dict) else getattr(tc, 'name', '')
                                        break
                                if last_tool_name:
                                    break
                    
                    # Build dynamic suggestion based on the tool that caused the overflow
                    tool_suggestions = self._get_tool_truncation_suggestions(last_tool_name)
                    
                    # Truncate the problematic tool result if found
                    if last_tool_msg_idx is not None:
                        from langchain_core.messages import ToolMessage
                        original_msg = new_messages[last_tool_msg_idx]
                        tool_call_id = getattr(original_msg, 'tool_call_id', 'unknown')
                        
                        # Build error-specific guidance
                        if is_output_limit_error:
                            truncated_content = (
                                f"⚠️ MODEL OUTPUT LIMIT EXCEEDED\n\n"
                                f"The tool '{last_tool_name or 'unknown'}' returned data, but the model's response was too large.\n\n"
                                f"IMPORTANT: You must provide a SMALLER, more focused response.\n"
                                f"- Break down your response into smaller chunks\n"
                                f"- Summarize instead of listing everything\n"
                                f"- Focus on the most relevant information first\n"
                                f"- If listing items, show only top 5-10 most important\n\n"
                                f"Tool-specific tips:\n{tool_suggestions}\n\n"
                                f"Please retry with a more concise response."
                            )
                        else:
                            truncated_content = (
                                f"⚠️ TOOL OUTPUT TRUNCATED - Context window exceeded\n\n"
                                f"The tool '{last_tool_name or 'unknown'}' returned too much data for the model's context window.\n\n"
                                f"To fix this:\n{tool_suggestions}\n\n"
                                f"Please retry with more restrictive parameters."
                            )
                        
                        truncated_msg = ToolMessage(
                            content=truncated_content,
                            tool_call_id=tool_call_id
                        )
                        new_messages[last_tool_msg_idx] = truncated_msg
                        
                        logger.info(f"Truncated large tool result from '{last_tool_name}' and continuing")
                        # Continue to next iteration - the model will see the truncation message
                        continue
                    else:
                        # Couldn't find tool message, add error and break
                        if is_output_limit_error:
                            error_msg = (
                                "Model output limit exceeded. Please provide a more concise response. "
                                "Break down your answer into smaller parts and summarize where possible."
                            )
                        else:
                            error_msg = (
                                "Context window exceeded. The conversation or tool results are too large. "
                                "Try using tools with smaller output limits (e.g., max_items, max_depth parameters)."
                            )
                        new_messages.append(AIMessage(content=error_msg))
                        break
                else:
                    logger.error(f"Error in LLM call during iteration {iteration}: {e}")
                    # Add error message and break the loop
                    error_msg = f"Error processing tool results in iteration {iteration}: {str(e)}"
                    new_messages.append(AIMessage(content=error_msg))
                    break

        # Handle max iterations
        if iteration >= self.steps_limit:
            logger.warning(f"Reached maximum iterations ({self.steps_limit}) for tool execution")
            
            # CRITICAL: Check if the last message is an AIMessage with pending tool_calls
            # that were not processed. If so, we need to add placeholder ToolMessages to prevent
            # the "assistant message with 'tool_calls' must be followed by tool messages" error
            # when the conversation continues.
            if new_messages:
                last_msg = new_messages[-1]
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    from langchain_core.messages import ToolMessage
                    pending_tool_calls = last_msg.tool_calls if hasattr(last_msg.tool_calls, '__iter__') else []
                    
                    # Check which tool_call_ids already have responses
                    existing_tool_call_ids = set()
                    for msg in new_messages:
                        if hasattr(msg, 'tool_call_id'):
                            existing_tool_call_ids.add(msg.tool_call_id)
                    
                    # Add placeholder responses for any tool calls without responses
                    for tool_call in pending_tool_calls:
                        tool_call_id = tool_call.get('id', '') if isinstance(tool_call, dict) else getattr(tool_call, 'id', '')
                        tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                        
                        if tool_call_id and tool_call_id not in existing_tool_call_ids:
                            logger.info(f"Adding placeholder ToolMessage for interrupted tool call: {tool_name} ({tool_call_id})")
                            placeholder_msg = ToolMessage(
                                content=f"[Tool execution interrupted - step limit ({self.steps_limit}) reached before {tool_name} could be executed]",
                                tool_call_id=tool_call_id
                            )
                            new_messages.append(placeholder_msg)
            
            # Add warning message - CLI or calling code can detect this and prompt user
            warning_msg = f"Maximum tool execution iterations ({self.steps_limit}) reached. Stopping tool execution."
            new_messages.append(AIMessage(content=warning_msg))
        else:
            logger.info(f"Tool execution completed after {iteration} iterations")

        return new_messages, current_completion

    def __get_struct_output_model(self, llm_client, pydantic_model, method: Literal["function_calling", "json_mode", "json_schema"] = "json_schema"):
        return llm_client.with_structured_output(pydantic_model, method=method)
