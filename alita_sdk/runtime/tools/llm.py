import asyncio
import logging
from traceback import format_exc
from typing import Any, Optional, List, Union, Literal

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from langchain_core.callbacks import dispatch_custom_event
from pydantic import Field

from ..langchain.constants import ELITEA_RS
from ..langchain.utils import create_pydantic_model, propagate_the_input_mapping

logger = logging.getLogger(__name__)


# def _is_thinking_model(llm_client: Any) -> bool:
#     """
#     Check if a model uses extended thinking capability by reading cached metadata.
    
#     Thinking models require special message formatting where assistant messages
#     must start with thinking blocks before tool_use blocks.
    
#     This function reads the `_supports_reasoning` attribute that should be set
#     when the LLM client is created (by checking the model's supports_reasoning field).
    
#     Args:
#         llm_client: LLM client instance with optional _supports_reasoning attribute
        
#     Returns:
#         True if the model is a thinking model, False otherwise
#     """
#     if not llm_client:
#         return False
    
#     # Check if supports_reasoning was cached on the client
#     supports_reasoning = getattr(llm_client, '_supports_reasoning', False)
    
#     if supports_reasoning:
#         model_name = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'unknown')
#         logger.debug(f"Model '{model_name}' is a thinking/reasoning model (cached from API metadata)")
    
#     return supports_reasoning

JSON_INSTRUCTION_TEMPLATE = (
        "\n\n**IMPORTANT: You MUST respond with ONLY a valid JSON object.**\n\n"
        "Required JSON fields:\n{field_descriptions}\n\n"
        "Example format:\n"
        "{{\n{example_fields}\n}}\n\n"
        "Rules:\n"
        "1. Output ONLY the JSON object - no markdown, no explanations, no extra text\n"
        "2. Ensure all required fields are present\n"
        "3. Use proper JSON syntax with double quotes for strings\n"
        "4. Do not wrap the JSON in code blocks or backticks"
    )

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

    def _prepare_structured_output_params(self) -> dict:
        """
        Prepare structured output parameters from structured_output_dict.

        Returns:
            Dictionary with parameter definitions for creating Pydantic model
        """
        struct_params = {
            key: {
                "type": 'list[str]' if 'list' in value else value,
                "description": ""
            }
            for key, value in (self.structured_output_dict or {}).items()
        }
        # Add default output field for proper response to user
        struct_params[ELITEA_RS] = {
            'description': 'final output to user (summarized output from LLM)',
            'type': 'str',
            "default": None
        }
        return struct_params

    def _invoke_with_structured_output(self, llm_client: Any, messages: List, struct_model: Any, config: RunnableConfig):
        """
        Invoke LLM with structured output, handling tool calls if present.

        Args:
            llm_client: LLM client instance
            messages: List of conversation messages
            struct_model: Pydantic model for structured output
            config: Runnable configuration

        Returns:
            Tuple of (completion, initial_completion, final_messages)
        """
        initial_completion = llm_client.invoke(messages, config=config)

        if hasattr(initial_completion, 'tool_calls') and initial_completion.tool_calls:
            # Handle tool calls first, then apply structured output
            new_messages, _ = self._run_async_in_sync_context(
                self.__perform_tool_calling(initial_completion, messages, llm_client, config)
            )
            llm = self.__get_struct_output_model(llm_client, struct_model)
            completion = llm.invoke(new_messages, config=config)
            return completion, initial_completion, new_messages
        else:
            # Direct structured output without tool calls
            llm = self.__get_struct_output_model(llm_client, struct_model)
            completion = llm.invoke(messages, config=config)
            return completion, initial_completion, messages

    def _build_json_instruction(self, struct_model: Any) -> str:
        """
        Build JSON instruction message for fallback handling.

        Args:
            struct_model: Pydantic model with field definitions

        Returns:
            Formatted JSON instruction string
        """
        field_descriptions = []
        for name, field in struct_model.model_fields.items():
            field_type = field.annotation.__name__ if hasattr(field.annotation, '__name__') else str(field.annotation)
            field_desc = field.description or field_type
            field_descriptions.append(f"  - {name} ({field_type}): {field_desc}")

        example_fields = ",\n".join([
            f'  "{k}": <{field.annotation.__name__ if hasattr(field.annotation, "__name__") else "value"}>'
            for k, field in struct_model.model_fields.items()
        ])

        return JSON_INSTRUCTION_TEMPLATE.format(
            field_descriptions="\n".join(field_descriptions),
            example_fields=example_fields
        )

    def _create_fallback_completion(self, content: str, struct_model: Any) -> Any:
        """
        Create a fallback completion object when JSON parsing fails.

        Args:
            content: Plain text content from LLM
            struct_model: Pydantic model to construct

        Returns:
            Pydantic model instance with fallback values
        """
        result_dict = {}
        for k, field in struct_model.model_fields.items():
            if k == ELITEA_RS:
                result_dict[k] = content
            elif field.is_required():
                # Set default values for required fields based on type
                result_dict[k] = field.default if field.default is not None else None
            else:
                result_dict[k] = field.default
        return struct_model.model_construct(**result_dict)

    def _handle_structured_output_fallback(self, llm_client: Any, messages: List, struct_model: Any,
                                          config: RunnableConfig, original_error: Exception) -> Any:
        """
        Handle structured output fallback through multiple strategies.

        Tries fallback methods in order:
        1. json_mode with explicit instructions
        2. function_calling method
        3. Plain text with JSON extraction

        Args:
            llm_client: LLM client instance
            messages: Original conversation messages
            struct_model: Pydantic model for structured output
            config: Runnable configuration
            original_error: The original ValueError that triggered fallback

        Returns:
            Completion with structured output (best effort)

        Raises:
            Propagates exceptions from LLM invocation
        """
        logger.error(f"Error invoking structured output model: {format_exc()}")
        logger.info("Attempting to fall back to json mode")

        # Build JSON instruction once
        json_instruction = self._build_json_instruction(struct_model)

        # Add instruction to messages
        modified_messages = messages.copy()
        if modified_messages and isinstance(modified_messages[-1], HumanMessage):
            modified_messages[-1] = HumanMessage(
                content=modified_messages[-1].content + json_instruction
            )
        else:
            modified_messages.append(HumanMessage(content=json_instruction))

        # Try json_mode with explicit instructions
        try:
            completion = self.__get_struct_output_model(
                llm_client, struct_model, method="json_mode"
            ).invoke(modified_messages, config=config)
            return completion
        except Exception as json_mode_error:
            logger.warning(f"json_mode also failed: {json_mode_error}")
            logger.info("Falling back to function_calling method")

            # Try function_calling as a third fallback
            try:
                completion = self.__get_struct_output_model(
                    llm_client, struct_model, method="function_calling"
                ).invoke(modified_messages, config=config)
                return completion
            except Exception as function_calling_error:
                logger.error(f"function_calling also failed: {function_calling_error}")
                logger.info("Final fallback: using plain LLM response")

                # Last resort: get plain text response and wrap in structure
                plain_completion = llm_client.invoke(modified_messages, config=config)
                content = plain_completion.content.strip() if hasattr(plain_completion, 'content') else str(plain_completion)

                # Try to extract JSON from the response
                import json
                import re

                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        parsed_json = json.loads(json_match.group(0))
                        # Validate it has expected fields and wrap in pydantic model
                        completion = struct_model(**parsed_json)
                        return completion
                    except (json.JSONDecodeError, Exception) as parse_error:
                        logger.warning(f"Could not parse extracted JSON: {parse_error}")
                        return self._create_fallback_completion(content, struct_model)
                else:
                    # No JSON found, create response with content in elitea_response
                    return self._create_fallback_completion(content, struct_model)

    def _format_structured_output_result(self, result: dict, messages: List, initial_completion: Any) -> dict:
        """
        Format structured output result with properly formatted messages.

        Args:
            result: Result dictionary from model_dump()
            messages: Original conversation messages
            initial_completion: Initial completion before tool calls

        Returns:
            Formatted result dictionary with messages
        """
        # Ensure messages are properly formatted
        if result.get('messages') and isinstance(result['messages'], list):
            result['messages'] = [{'role': 'assistant', 'content': '\n'.join(result['messages'])}]
        else:
            # Extract content from initial_completion, handling thinking blocks
            fallback_content = result.get(ELITEA_RS, '')
            if not fallback_content and initial_completion:
                content_parts = self._extract_content_from_completion(initial_completion)
                fallback_content = content_parts.get('text') or ''
                thinking = content_parts.get('thinking')

                # Log thinking if present
                if thinking:
                    logger.debug(f"Thinking content present in structured output: {thinking[:100]}...")

                if not fallback_content:
                    # Final fallback to raw content
                    content = initial_completion.content
                    fallback_content = content if isinstance(content, str) else str(content)

            result['messages'] = messages + [AIMessage(content=fallback_content)]

        return result

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
                struct_params = self._prepare_structured_output_params()
                struct_model = create_pydantic_model(f"LLMOutput", struct_params)

                try:
                    completion, initial_completion, final_messages = self._invoke_with_structured_output(
                        llm_client, messages, struct_model, config
                    )
                except ValueError as e:
                    # Handle fallback for structured output failures
                    completion = self._handle_structured_output_fallback(
                        llm_client, messages, struct_model, config, e
                    )
                    initial_completion = None
                    final_messages = messages

                result = completion.model_dump()
                result = self._format_structured_output_result(result, final_messages, initial_completion or completion)

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
                        # Extract content properly from thinking-enabled responses
                        if current_completion:
                            content_parts = self._extract_content_from_completion(current_completion)
                            text_content = content_parts.get('text')
                            thinking = content_parts.get('thinking')
                            
                            # Dispatch thinking event if present
                            if thinking:
                                try:
                                    model_name = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'LLM')
                                    dispatch_custom_event(
                                        name="thinking_step",
                                        data={
                                            "message": thinking,
                                            "tool_name": f"LLM ({model_name})",
                                            "toolkit": "reasoning",
                                        },
                                        config=config,
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to dispatch thinking event: {e}")
                            
                            if text_content:
                                output_msgs[self.output_variables[0]] = text_content
                            else:
                                # Fallback to raw content
                                content = current_completion.content
                                output_msgs[self.output_variables[0]] = content if isinstance(content, str) else str(content)
                        else:
                            output_msgs[self.output_variables[0]] = None

                    return output_msgs
                else:
                    # Regular text response - handle both simple strings and thinking-enabled responses
                    content_parts = self._extract_content_from_completion(completion)
                    thinking = content_parts.get('thinking')
                    text_content = content_parts.get('text') or ''
                    
                    # Fallback to string representation if no content extracted
                    if not text_content:
                        if hasattr(completion, 'content'):
                            content = completion.content
                            text_content = content.strip() if isinstance(content, str) else str(content)
                        else:
                            text_content = str(completion)
                    
                    # Dispatch thinking step event to chat if present
                    if thinking:
                        logger.info(f"Model thinking: {thinking[:200]}..." if len(thinking) > 200 else f"Model thinking: {thinking}")
                        
                        # Dispatch custom event for thinking step to be displayed in chat
                        try:
                            model_name = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'LLM')
                            dispatch_custom_event(
                                name="thinking_step",
                                data={
                                    "message": thinking,
                                    "tool_name": f"LLM ({model_name})",
                                    "toolkit": "reasoning",
                                },
                                config=config,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to dispatch thinking event: {e}")
                    
                    # Build the AI message with both thinking and text
                    # Store thinking in additional_kwargs for potential future use
                    ai_message_kwargs = {'content': text_content}
                    if thinking:
                        ai_message_kwargs['additional_kwargs'] = {'thinking': thinking}
                    ai_message = AIMessage(**ai_message_kwargs)

                    # Try to extract JSON if output variables are specified (but exclude 'messages' which is handled separately)
                    json_output_vars = [var for var in (self.output_variables or []) if var != 'messages']
                    if json_output_vars:
                        # set response to be the first output variable for non-structured output
                        response_data = {json_output_vars[0]: text_content}
                        new_messages = messages + [ai_message]
                        response_data['messages'] = new_messages
                        return response_data

                    # Simple text response (either no output variables or JSON parsing failed)
                    new_messages = messages + [ai_message]
                    return {"messages": new_messages}

        except Exception as e:
            # Enhanced error logging with model diagnostics
            model_info = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'unknown')
            logger.error(f"Error in LLM Node: {format_exc()}")
            logger.error(f"Model being used: {model_info}")
            logger.error(f"Error type: {type(e).__name__}")
            
            error_msg = f"Error: {e}"
            new_messages = messages + [AIMessage(content=error_msg)]
            return {"messages": new_messages}

    def _run(self, *args, **kwargs):
        # Legacy support for old interface
        return self.invoke(kwargs, **kwargs)
    
    @staticmethod
    def _extract_content_from_completion(completion) -> dict:
        """Extract thinking and text content from LLM completion.
        
        Handles Anthropic's extended thinking format where content is a list
        of blocks with types: 'thinking' and 'text'.
        
        Args:
            completion: LLM completion object with content attribute
            
        Returns:
            dict with 'thinking' and 'text' keys
        """
        result = {'thinking': None, 'text': None}
        
        if not hasattr(completion, 'content'):
            return result
            
        content = completion.content
        
        # Handle list of content blocks (Anthropic extended thinking format)
        if isinstance(content, list):
            thinking_blocks = []
            text_blocks = []
            
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get('type', '')
                    if block_type == 'thinking':
                        thinking_blocks.append(block.get('thinking', ''))
                    elif block_type == 'text':
                        text_blocks.append(block.get('text', ''))
                elif hasattr(block, 'type'):
                    # Handle object format
                    if block.type == 'thinking':
                        thinking_blocks.append(getattr(block, 'thinking', ''))
                    elif block.type == 'text':
                        text_blocks.append(getattr(block, 'text', ''))
            
            if thinking_blocks:
                result['thinking'] = '\n\n'.join(thinking_blocks)
            if text_blocks:
                result['text'] = '\n\n'.join(text_blocks)
        
        # Handle simple string content
        elif isinstance(content, str):
            result['text'] = content
        
        return result
    
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
        
        # Check if this is a thinking model - they require special message handling
        # model_name = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', '')
        # if _is_thinking_model(llm_client):
        #     logger.warning(
        #         f"⚠️ THINKING/REASONING MODEL DETECTED: '{model_name}'\n"
        #         f"Tool execution with thinking models may fail due to message format requirements.\n"
        #         f"Thinking models require 'thinking_blocks' to be preserved between turns, which this "
        #         f"framework cannot do.\n"
        #         f"Recommendation: Use standard model variants (e.g., claude-3-5-sonnet-20241022-v2:0) "
        #         f"instead of thinking/reasoning variants for tool calling.\n"
        #         f"See: https://docs.litellm.ai/docs/reasoning_content"
        #     )
        
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
                
                # Check for thinking model message format errors
                is_thinking_format_error = any(indicator in error_str for indicator in [
                    'expected `thinking`',
                    'expected `redacted_thinking`',
                    'thinking block',
                    'must start with a thinking block',
                    'when `thinking` is enabled'
                ])
                
                # Check for non-recoverable errors that should fail immediately
                # These indicate configuration or permission issues, not content size issues
                is_non_recoverable = any(indicator in error_str for indicator in [
                    'model identifier is invalid',
                    'authentication',
                    'unauthorized',
                    'access denied',
                    'permission denied',
                    'invalid credentials',
                    'api key',
                    'quota exceeded',
                    'rate limit'
                ])
                
                # Check for context window / token limit errors
                is_context_error = any(indicator in error_str for indicator in [
                    'context window', 'context_window', 'token limit', 'too long',
                    'maximum context length', 'input is too long', 'exceeds the limit',
                    'contextwindowexceedederror', 'max_tokens', 'content too large'
                ])
                
                # Check for Bedrock/Claude output limit errors (recoverable by truncation)
                is_output_limit_error = any(indicator in error_str for indicator in [
                    'output token',
                    'response too large',
                    'max_tokens_to_sample',
                    'output_token_limit',
                    'output exceeds'
                ])
                
                # Handle thinking model format errors
                if is_thinking_format_error:
                    model_info = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'unknown')
                    logger.error(f"Thinking model message format error during tool execution iteration {iteration}")
                    logger.error(f"Model: {model_info}")
                    logger.error(f"Error details: {e}")
                    
                    error_msg = (
                        f"⚠️ THINKING MODEL FORMAT ERROR\n\n"
                        f"The model '{model_info}' uses extended thinking and requires specific message formatting.\n\n"
                        f"**Issue**: When 'thinking' is enabled, assistant messages must start with thinking blocks "
                        f"before any tool_use blocks. This framework cannot preserve thinking_blocks during iterative "
                        f"tool execution.\n\n"
                        f"**Root Cause**: Anthropic's Messages API is stateless - clients must manually preserve and "
                        f"resend thinking_blocks with every tool response. LangChain's message abstraction doesn't "
                        f"include thinking_blocks, so they are lost between turns.\n\n"
                        f"**Solutions**:\n"
                        f"1. **Recommended**: Use non-thinking model variants:\n"
                        f"   - claude-3-5-sonnet-20241022-v2:0 (instead of thinking variants)\n"
                        f"   - anthropic.claude-3-5-sonnet-20241022-v2:0 (Bedrock)\n"
                        f"2. Disable extended thinking: Set reasoning_effort=None or remove thinking config\n"
                        f"3. Use LiteLLM directly with modify_params=True (handles thinking_blocks automatically)\n"
                        f"4. Avoid tool calling with thinking models (use for reasoning tasks only)\n\n"
                        f"**Technical Context**: {str(e)}\n\n"
                        f"References:\n"
                        f"- https://docs.claude.com/en/docs/build-with-claude/extended-thinking\n"
                        f"- https://docs.litellm.ai/docs/reasoning_content (See 'Tool Calling with thinking' section)"
                    )
                    new_messages.append(AIMessage(content=error_msg))
                    raise ValueError(error_msg)
                
                # Handle non-recoverable errors immediately
                if is_non_recoverable:
                    # Enhanced error logging with model information for better diagnostics
                    model_info = getattr(llm_client, 'model_name', None) or getattr(llm_client, 'model', 'unknown')
                    logger.error(f"Non-recoverable error during tool execution iteration {iteration}")
                    logger.error(f"Model: {model_info}")
                    logger.error(f"Error details: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    
                    # Provide detailed error message for debugging
                    error_details = []
                    error_details.append(f"Model configuration error: {str(e)}")
                    error_details.append(f"Model identifier: {model_info}")
                    
                    # Check for common Bedrock model ID issues
                    if 'model identifier is invalid' in error_str:
                        error_details.append("\nPossible causes:")
                        error_details.append("1. Model not available in the configured AWS region")
                        error_details.append("2. Model not enabled in your AWS Bedrock account")
                        error_details.append("3. LiteLLM model group prefix not stripped (check for prefixes like '1_')")
                        error_details.append("4. Incorrect model version or typo in model name")
                        error_details.append("\nPlease verify:")
                        error_details.append("- AWS Bedrock console shows this model as available")
                        error_details.append("- LiteLLM router configuration is correct")
                        error_details.append("- Model ID doesn't contain unexpected prefixes")
                    
                    error_msg = "\n".join(error_details)
                    new_messages.append(AIMessage(content=error_msg))
                    break
                
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
                        
                        logger.info(f"Truncated large tool result from '{last_tool_name}' and retrying LLM call")
                        
                        # CRITICAL FIX: Call LLM again with truncated message to get fresh completion
                        # This prevents duplicate tool_call_ids that occur when we continue with
                        # the same current_completion that still has the original tool_calls
                        try:
                            current_completion = llm_client.invoke(new_messages, config=config)
                            new_messages.append(current_completion)
                            
                            # Continue to process any new tool calls in the fresh completion
                            if hasattr(current_completion, 'tool_calls') and current_completion.tool_calls:
                                logger.info(f"LLM requested {len(current_completion.tool_calls)} more tool calls after truncation")
                                continue
                            else:
                                logger.info("LLM completed after truncation without requesting more tools")
                                break
                        except Exception as retry_error:
                            logger.error(f"Error retrying LLM after truncation: {retry_error}")
                            error_msg = f"Failed to retry after truncation: {str(retry_error)}"
                            new_messages.append(AIMessage(content=error_msg))
                            break
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
