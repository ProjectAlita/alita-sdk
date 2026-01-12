"""
Skill Router Wrapper for LangChain integration.

This module provides a wrapper that exposes the skills registry system
through multiple focused tools for listing, describing, and executing skills.
"""

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from ..skills import (
    SkillsRegistry, get_default_registry, SkillType,
    SkillExecutionResult, SkillStatus
)
from ..skills.executor import SkillExecutor
from ..skills.callbacks import CallbackManager, create_default_callbacks

logger = logging.getLogger(__name__)


# Input Schemas for the three separate tools
class ListSkillsInput(BaseModel):
    """Input schema for listing skills."""
    
    skill_type: Optional[Literal["graph", "agent"]] = Field(
        default=None,
        description="Filter skills by type when listing"
    )
    
    capability: Optional[str] = Field(
        default=None,
        description="Filter skills by capability when listing"
    )
    
    tag: Optional[str] = Field(
        default=None,
        description="Filter skills by tag when listing"
    )


class DescribeSkillInput(BaseModel):
    """Input schema for describing a skill."""
    
    skill_name: str = Field(
        description="Name of the skill to describe (required)"
    )


class ExecuteSkillInput(BaseModel):
    """Input schema for executing a skill."""
    
    skill_name: Optional[str] = Field(
        default=None,
        description="Name of the skill to execute (optional - if not provided, LLM will select best skill)"
    )
    
    task: str = Field(
        description="Task or question for the skill (required)"
    )
    
    # Agent-specific inputs
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables/context for agent skills (key-value pairs)"
    )
    
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Chat conversation history for agent skills (list of {role: 'user'|'assistant', content: 'message'})"
    )
    
    # Graph-specific inputs
    state_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="State variables for graph skills (key-value pairs)"
    )
    
    # Execution options
    execution_mode: Optional[Literal["subprocess", "remote"]] = Field(
        default=None,
        description="Override execution mode (subprocess or remote)"
    )
    
    enable_callbacks: bool = Field(
        default=False,
        description="Enable real-time callback events during execution"
    )


class SkillRouterWrapper(BaseToolApiWrapper):
    """
    Wrapper for skill registry operations.
    
    This wrapper provides methods for listing, describing, and executing skills
    with intelligent routing capabilities and proper input handling.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Declare Pydantic fields for the wrapper components
    registry: Optional[SkillsRegistry] = Field(default=None)
    executor: Optional[SkillExecutor] = Field(default=None)
    enable_callbacks: bool = Field(default=True)
    
    # Router-level configuration
    default_timeout: Optional[int] = Field(default=None)
    default_execution_mode: Optional[str] = Field(default=None)
    llm: Optional[Any] = Field(default=None, description="LLM for intelligent skill selection")
    custom_prompt: Optional[str] = Field(default=None, description="Custom prompt for skill routing")
    
    # Private attribute for callback manager (not a Pydantic field)
    _callback_manager: Optional[CallbackManager] = None
    
    def __init__(
        self,
        registry: Optional[SkillsRegistry] = None,
        alita_client=None,
        llm=None,
        enable_callbacks: bool = True,
        default_timeout: Optional[int] = None,
        default_execution_mode: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the Skill Router wrapper.
        
        Args:
            registry: Skills registry instance. If None, uses default registry.
            alita_client: AlitaClient for LLM access and remote execution.
            llm: Language model for intelligent skill selection.
            enable_callbacks: Whether to enable callback system by default.
            default_timeout: Default timeout for skill execution.
            default_execution_mode: Default execution mode for skills.
            custom_prompt: Custom prompt for skill routing.
            **kwargs: Additional arguments.
        """
        # Initialize components
        registry_instance = registry or get_default_registry()
        executor_instance = SkillExecutor(alita_client)
        
        # Initialize the Pydantic model with declared fields only
        super().__init__(
            registry=registry_instance,
            executor=executor_instance,
            enable_callbacks=enable_callbacks,
            default_timeout=default_timeout,
            default_execution_mode=default_execution_mode,
            llm=llm,
            custom_prompt=custom_prompt,
            **kwargs
        )
        
        # Initialize callback manager as private attribute
        self._callback_manager = CallbackManager()
        if enable_callbacks:
            # Add default callbacks
            for callback in create_default_callbacks():
                self._callback_manager.add_callback(callback)
        
        logger.info("SkillRouterWrapper initialized")
    
    def get_available_tools(self):
        """
        Get the list of available tools provided by this wrapper.
        
        Returns:
            List of tool definitions with name, description, args_schema, and ref.
        """
        return [
            {
                "name": "list_skills",
                "description": """List all available skills in the registry with optional filtering.

Use this tool to discover what skills are available for execution. You can filter by:
- skill_type: Filter by 'agent' or 'graph' skills
- capability: Filter by specific capability (e.g., 'jira', 'analysis')
- tag: Filter by tag

Skills come in two types:
- Agent skills: Conversational, use variables and chat history
- Graph skills: State-based workflows, use state variables

Examples:
- List all skills: {}
- List agent skills: {"skill_type": "agent"}
- List skills with Jira capability: {"capability": "jira"}
""",
                "args_schema": ListSkillsInput,
                "ref": self._handle_list
            },
            {
                "name": "describe_skill",
                "description": """Get detailed information about a specific skill.

Use this tool to understand a skill's inputs, capabilities, and how to execute it.
Provides complete documentation including:
- Input schema and required/optional parameters
- Capabilities and tags
- Execution configuration
- Usage examples

Example: {"skill_name": "jira_triage"}
""",
                "args_schema": DescribeSkillInput,
                "ref": self._handle_describe
            },
            {
                "name": "execute_skill",
                "description": """Execute a specialized skill to perform a complex task.

This tool provides access to specialized skills with intelligent routing capabilities.
When skill_name is not specified, the LLM will automatically select the best skill 
based on the task description.

Skills come in two types:
- Agent skills: Use 'context' and 'chat_history' parameters
- Graph skills: Use 'state_variables' parameter

Execution modes:
- subprocess: Run skills locally in isolated processes (filesystem skills)
- remote: Run skills via platform APIs (platform-hosted skills)

Examples:
- Auto-select skill: {"task": "Analyze issue PROJ-123"}
- Explicit skill: {"skill_name": "jira_triage", "task": "Analyze issue", "context": {"issue_key": "PROJ-123"}}
- Override mode: {"skill_name": "my_skill", "task": "Process data", "execution_mode": "remote"}
""",
                "args_schema": ExecuteSkillInput,
                "ref": self._handle_execute
            }
        ]
    
    def _handle_list(
        self,
        skill_type: Optional[str] = None,
        capability: Optional[str] = None,
        tag: Optional[str] = None
    ) -> str:
        """Handle list skills operation."""
        try:
            # Get all skills
            skills = self.registry.list()
            
            # Apply filters
            if skill_type:
                skills = [s for s in skills if (s.skill_type.value if hasattr(s.skill_type, 'value') else str(s.skill_type)) == skill_type]
            if capability:
                skills = [s for s in skills if capability in s.capabilities]
            if tag:
                skills = [s for s in skills if tag in s.tags]
            
            if not skills:
                return "No skills found matching the specified criteria."
            
            # Format results
            result = f"Found {len(skills)} skills:\n\n"
            
            for skill in skills:
                skill_type_str = skill.skill_type.value if hasattr(skill.skill_type, 'value') else str(skill.skill_type)
                result += f"**{skill.name}** ({skill_type_str})\n"
                result += f"  Description: {skill.description}\n"
                
                if skill.capabilities:
                    result += f"  Capabilities: {', '.join(skill.capabilities)}\n"
                
                if skill.tags:
                    result += f"  Tags: {', '.join(skill.tags)}\n"
                
                result += f"  Version: {skill.version}\n\n"
            
            # Add summary stats
            stats = self.registry.get_registry_stats()
            result += f"\n**Registry Stats:**\n"
            result += f"- Total skills: {stats['total_skills']}\n"
            result += f"- Graph skills: {stats['graph_skills']}\n"
            result += f"- Agent skills: {stats['agent_skills']}\n"
            result += f"- Unique capabilities: {stats['unique_capabilities']}\n"
            
            return result
        
        except Exception as e:
            return f"Error listing skills: {str(e)}"
    
    def _handle_describe(self, skill_name: str) -> str:
        """Handle describe skill operation."""
        try:
            skill = self.registry.get(skill_name)
            if not skill:
                available_skills = [s.name for s in self.registry.list()]
                return (f"Skill '{skill_name}' not found. "
                       f"Available skills: {', '.join(available_skills)}")
            
            # Build detailed description
            skill_type_str = skill.skill_type.value if hasattr(skill.skill_type, 'value') else str(skill.skill_type)
            result = f"# {skill.name} ({skill_type_str} skill)\n\n"
            result += f"**Description:** {skill.description}\n\n"
            
            # Basic info
            result += f"**Version:** {skill.version}\n"
            execution_mode_str = skill.execution.mode.value if hasattr(skill.execution.mode, 'value') else str(skill.execution.mode)
            result += f"**Execution Mode:** {execution_mode_str}\n"
            result += f"**Timeout:** {skill.execution.timeout}s\n\n"
            
            # Capabilities and tags
            if skill.capabilities:
                result += f"**Capabilities:** {', '.join(skill.capabilities)}\n"
            if skill.tags:
                result += f"**Tags:** {', '.join(skill.tags)}\n\n"
            
            # Input schema
            result += "**Input Schema:**\n"
            if skill.skill_type == SkillType.AGENT:
                result += "- **task** (required): Task or question for the skill\n"
                result += "- **context** (optional): Variables as key-value pairs\n"
                result += "- **chat_history** (optional): Conversation history\n"
                
                if skill.inputs.variables:
                    result += "\n**Available Variables:**\n"
                    for var_name, var_def in skill.inputs.variables.items():
                        var_type = var_def.get('type', 'any')
                        var_desc = var_def.get('description', '')
                        required = ' (required)' if var_def.get('required') else ''
                        result += f"- **{var_name}** ({var_type}){required}: {var_desc}\n"
            
            else:  # GRAPH
                result += "- **task** (required): Task description (becomes 'input' state variable)\n"
                result += "- **state_variables** (optional): State variables as key-value pairs\n"
                
                if skill.inputs.state_variables:
                    result += "\n**Available State Variables:**\n"
                    for var_name, var_def in skill.inputs.state_variables.items():
                        var_type = var_def.get('type', 'any')
                        var_desc = var_def.get('description', '')
                        required = ' (required)' if var_def.get('required') else ''
                        result += f"- **{var_name}** ({var_type}){required}: {var_desc}\n"
            
            # LLM settings
            if skill.model or skill.temperature or skill.max_tokens:
                result += "\n**LLM Configuration:**\n"
                if skill.model:
                    result += f"- Model: {skill.model}\n"
                if skill.temperature:
                    result += f"- Temperature: {skill.temperature}\n"
                if skill.max_tokens:
                    result += f"- Max tokens: {skill.max_tokens}\n"
            
            # Usage example
            result += "\n**Usage Example:**\n"
            if skill.skill_type == SkillType.AGENT:
                example = {
                    "skill_name": skill.name,
                    "task": f"Your task description here",
                    "context": {"key": "value"}
                }
            else:
                example = {
                    "skill_name": skill.name,
                    "task": f"Your task description here",
                    "state_variables": {"key": "value"}
                }
            
            result += f"```json\n{json.dumps(example, indent=2)}\n```"
            
            return result
        
        except Exception as e:
            return f"Error describing skill: {str(e)}"
    
    def _handle_execute(
        self,
        task: str,
        skill_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        state_variables: Optional[Dict[str, Any]] = None,
        execution_mode: Optional[str] = None,
        enable_callbacks: bool = False
    ) -> str:
        """Handle execute skill operation with comprehensive input validation."""
        # If no skill_name provided, use LLM to intelligently select the best skill
        if not skill_name:
            skill_name = self._select_skill_with_llm(task)
            if not skill_name:
                return "Error: No appropriate skill found for the given task."
        
        try:
            # Get skill metadata
            skill = self.registry.get(skill_name)
            if not skill:
                available_skills = [s.name for s in self.registry.list()]
                return (f"Skill '{skill_name}' not found. "
                       f"Available skills: {', '.join(available_skills)}")
            
            # Validate inputs against skill expectations
            validation_result = self._validate_skill_inputs(skill, context, state_variables, chat_history)
            if validation_result:
                return validation_result  # Return validation error message
            
            # Apply router-level defaults and overrides
            # 1. Apply router-level default timeout if not already set
            if self.default_timeout and skill.execution.timeout == 300:  # 300 is system default
                skill.execution.timeout = self.default_timeout
            
            # 2. Apply router-level default execution mode if not already set
            if self.default_execution_mode and not execution_mode:
                execution_mode = self.default_execution_mode
            
            # 3. Override execution mode if specified in input (takes priority)
            if execution_mode:
                skill.execution.mode = execution_mode
            
            # Determine input based on skill type
            if skill.skill_type == SkillType.AGENT:
                skill_context = context
                skill_chat_history = chat_history
            else:  # GRAPH
                # For graphs, merge task into state variables
                skill_context = state_variables or {}
                skill_chat_history = None
            
            # Execute the skill
            result = self.executor.execute_skill(
                metadata=skill,
                task=task,
                context=skill_context,
                chat_history=skill_chat_history
            )
            
            # Format result for LLM consumption
            return self._format_execution_result(result)
        
        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            return f"Error executing skill '{skill_name}': {str(e)}"
    
    def _select_skill_with_llm(self, task: str) -> Optional[str]:
        """Use LLM to intelligently select the best skill for a given task."""
        if not self.llm or not task:
            logger.warning("LLM or task not available for skill selection")
            return None
        
        try:
            # Get available skills for LLM to choose from
            skills = self.registry.list()
            if not skills:
                logger.warning("No skills available for selection")
                return None
            
            # Format skills list for the prompt
            skills_list = []
            for skill in skills:
                skill_info = f"- {skill.name}"
                if skill.description:
                    skill_info += f": {skill.description}"
                if skill.capabilities:
                    skill_info += f" (capabilities: {', '.join(skill.capabilities)})"
                skills_list.append(skill_info)
            
            skills_text = "\n".join(skills_list)
            
            # Create routing prompt - use custom_prompt if provided, otherwise default
            if self.custom_prompt:
                # If custom prompt provided, combine it with routing instructions
                routing_template = f"""{self.custom_prompt}

Your task is to analyze the user's request and select the most appropriate skill from the available options.

Available skills:
{{skills_list}}

Task: {{task}}

IMPORTANT: Respond with only the skill name that best matches the task. If no skill is appropriate, respond with "no_match"."""
            else:
                # Use default routing prompt
                routing_template = """You are a skill router. Analyze the user's task and select the most appropriate skill.

Available skills:
{skills_list}

Task: {task}

Respond with only the skill name that best matches the task. If no skill is appropriate, respond with "no_match"."""
            
            # Format the routing prompt
            formatted_prompt = routing_template.format(
                skills_list=skills_text,
                task=task
            )
            
            logger.info(f"Using LLM to select skill for task: {task}")
            
            # Get LLM response
            response = self.llm.invoke(formatted_prompt)
            if hasattr(response, 'content'):
                selected_skill = response.content.strip()
            else:
                selected_skill = str(response).strip()
            
            # Validate that the selected skill exists
            if selected_skill == "no_match":
                logger.info("LLM determined no skill matches the task")
                return None
            
            # Check if the selected skill actually exists
            skill = self.registry.get(selected_skill)
            if skill:
                logger.info(f"LLM selected skill: {selected_skill}")
                return selected_skill
            else:
                logger.warning(f"LLM selected non-existent skill: {selected_skill}")
                return None
        
        except Exception as e:
            logger.error(f"Error in LLM skill selection: {e}")
            return None
    
    def _validate_skill_inputs(
        self,
        skill,
        context: Optional[Dict[str, Any]],
        state_variables: Optional[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]]
    ) -> Optional[str]:
        """
        Validate inputs against skill expectations and provide graceful error messages.
        
        Returns:
            None if validation passes, error message string if validation fails.
        """
        try:
            if skill.skill_type == SkillType.AGENT:
                return self._validate_agent_inputs(skill, context, chat_history)
            else:  # GRAPH
                return self._validate_graph_inputs(skill, state_variables)
        except Exception as e:
            logger.error(f"Input validation error: {e}")
            return f"Error validating inputs: {str(e)}"
    
    def _validate_agent_inputs(
        self,
        skill,
        context: Optional[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]]
    ) -> Optional[str]:
        """Validate inputs for agent skills."""
        # Validate chat history format if provided
        if chat_history and not isinstance(chat_history, list):
            return (f"❌ **Invalid chat_history format for skill '{skill.name}'**\n\n"
                   f"Chat history must be a list of messages.\n"
                   f"Expected format: [{{'role': 'user', 'content': 'message'}}]\n"
                   f"Got: {type(chat_history).__name__}")
        
        if chat_history:
            for i, msg in enumerate(chat_history):
                if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                    return (f"❌ **Invalid chat_history format for skill '{skill.name}'**\n\n"
                           f"Message at index {i} is invalid.\n"
                           f"Each message must have 'role' and 'content' keys.\n"
                           f"Expected: {{'role': 'user'|'assistant', 'content': 'message text'}}\n"
                           f"Got: {msg}")
        
        if not hasattr(skill.inputs, 'variables') or not skill.inputs.variables:
            return None  # No input requirements defined
        
        provided_context = context or {}
        missing_required = []
        invalid_types = []
        
        # Check each required variable
        for var_name, var_def in skill.inputs.variables.items():
            is_required = var_def.get('required', False)
            expected_type = var_def.get('type', 'any')
            
            if is_required and var_name not in provided_context:
                missing_required.append({
                    'name': var_name,
                    'type': expected_type,
                    'description': var_def.get('description', '')
                })
            elif var_name in provided_context and expected_type != 'any':
                # Validate type if specified and value is provided
                provided_value = provided_context[var_name]
                if not self._validate_type(provided_value, expected_type):
                    invalid_types.append({
                        'name': var_name,
                        'expected': expected_type,
                        'provided': type(provided_value).__name__,
                        'value': str(provided_value)[:50]
                    })
        
        # Build error message if there are issues
        if missing_required or invalid_types:
            error_msg = f"❌ **Input validation failed for skill '{skill.name}'**\n\n"
            
            if missing_required:
                error_msg += "**Missing required variables:**\n"
                for var in missing_required:
                    error_msg += f"- **{var['name']}** ({var['type']}): {var['description']}\n"
                error_msg += "\n"
            
            if invalid_types:
                error_msg += "**Type mismatches:**\n"
                for var in invalid_types:
                    error_msg += f"- **{var['name']}**: expected {var['expected']}, got {var['provided']} ('{var['value']}')\n"
                error_msg += "\n"
            
            # Provide correct usage example
            error_msg += "**Correct usage:**\n"
            example_context = {}
            for var_name, var_def in skill.inputs.variables.items():
                example_value = self._get_example_value(var_def.get('type', 'string'))
                example_context[var_name] = example_value
            
            example = {
                "skill_name": skill.name,
                "task": "Your task description here",
                "context": example_context
            }
            error_msg += f"```json\n{json.dumps(example, indent=2)}\n```"
            
            return error_msg
        
        return None
    
    def _validate_graph_inputs(
        self,
        skill,
        state_variables: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Validate inputs for graph skills."""
        if not hasattr(skill.inputs, 'state_variables') or not skill.inputs.state_variables:
            return None  # No input requirements defined
        
        provided_state = state_variables or {}
        missing_required = []
        invalid_types = []
        
        # Check each required state variable
        for var_name, var_def in skill.inputs.state_variables.items():
            is_required = var_def.get('required', False)
            expected_type = var_def.get('type', 'any')
            
            if is_required and var_name not in provided_state:
                missing_required.append({
                    'name': var_name,
                    'type': expected_type,
                    'description': var_def.get('description', '')
                })
            elif var_name in provided_state and expected_type != 'any':
                # Validate type if specified and value is provided
                provided_value = provided_state[var_name]
                if not self._validate_type(provided_value, expected_type):
                    invalid_types.append({
                        'name': var_name,
                        'expected': expected_type,
                        'provided': type(provided_value).__name__,
                        'value': str(provided_value)[:50]
                    })
        
        # Build error message if there are issues
        if missing_required or invalid_types:
            error_msg = f"❌ **Input validation failed for skill '{skill.name}'**\n\n"
            
            if missing_required:
                error_msg += "**Missing required state variables:**\n"
                for var in missing_required:
                    error_msg += f"- **{var['name']}** ({var['type']}): {var['description']}\n"
                error_msg += "\n"
            
            if invalid_types:
                error_msg += "**Type mismatches:**\n"
                for var in invalid_types:
                    error_msg += f"- **{var['name']}**: expected {var['expected']}, got {var['provided']} ('{var['value']}')\n"
                error_msg += "\n"
            
            # Provide correct usage example
            error_msg += "**Correct usage:**\n"
            example_state = {}
            for var_name, var_def in skill.inputs.state_variables.items():
                example_value = self._get_example_value(var_def.get('type', 'string'))
                example_state[var_name] = example_value
            
            example = {
                "skill_name": skill.name,
                "task": "Your task description here",
                "state_variables": example_state
            }
            error_msg += f"```json\n{json.dumps(example, indent=2)}\n```"
            
            return error_msg
        
        return None
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate that a value matches the expected type."""
        type_mapping = {
            'string': str,
            'str': str,
            'integer': int,
            'int': int,
            'number': (int, float),
            'float': float,
            'boolean': bool,
            'bool': bool,
            'list': list,
            'array': list,
            'dict': dict,
            'object': dict,
            'any': object  # Accept anything
        }
        
        expected_py_type = type_mapping.get(expected_type.lower(), str)
        return isinstance(value, expected_py_type)
    
    def _get_example_value(self, var_type: str) -> Any:
        """Generate example values for different types."""
        examples = {
            'string': 'example_value',
            'str': 'example_value',
            'integer': 42,
            'int': 42,
            'number': 42.0,
            'float': 42.0,
            'boolean': True,
            'bool': True,
            'list': ['item1', 'item2'],
            'array': ['item1', 'item2'],
            'dict': {'key': 'value'},
            'object': {'key': 'value'},
            'any': 'example_value'
        }
        return examples.get(var_type.lower(), 'example_value')
    
    def _format_execution_result(self, result: SkillExecutionResult) -> str:
        """
        Format execution result for LLM consumption.
        
        Args:
            result: SkillExecutionResult to format.
        
        Returns:
            Formatted string result.
        """
        if result.status == SkillStatus.ERROR:
            formatted = f"❌ **Skill '{result.skill_name}' failed**\n\n"
            formatted += f"Error: {result.error_details or 'Unknown error'}\n"
            formatted += f"Duration: {result.duration:.1f}s"
            return formatted

        # Start with the main output
        formatted = result.output_text

        # Add execution metadata
        formatted += f"\n\n---\n"
        formatted += f"**Execution Summary:**\n"
        skill_type_str = result.skill_type.value if hasattr(result.skill_type, 'value') else str(result.skill_type)
        status_str = result.status.value if hasattr(result.status, 'value') else str(result.status)
        execution_mode_str = result.execution_mode.value if hasattr(result.execution_mode, 'value') else str(result.execution_mode)
        formatted += f"- Skill: {result.skill_name} ({skill_type_str})\n"
        formatted += f"- Status: {status_str}\n"
        formatted += f"- Duration: {result.duration:.1f}s\n"
        formatted += f"- Mode: {execution_mode_str}\n"

        # Add file references if any
        if result.output_files:
            formatted += f"\n**Generated Files:**\n"
            for file_ref in result.output_files:
                formatted += f"- {file_ref}\n"

        return formatted
