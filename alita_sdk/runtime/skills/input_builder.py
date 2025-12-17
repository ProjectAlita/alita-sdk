"""
Input preparation for different skill types.

This module handles the preparation of input data for skill execution,
ensuring that inputs are properly formatted for agent vs graph skill types.
"""

import logging
from typing import Any, Dict, List, Optional

from .models import SkillMetadata, SkillType, SkillValidationError

logger = logging.getLogger(__name__)


class SkillInputBuilder:
    """
    Service for building properly formatted inputs for different skill types.

    This class handles the different input requirements for:
    - Agent skills: variables, chat_history, and user input
    - Graph skills: state variables with input field
    """

    @staticmethod
    def prepare_input(
        skill_metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Prepare input data based on skill type.

        Args:
            skill_metadata: Metadata for the skill being executed.
            task: The main task or user input for the skill.
            context: Additional context data (variables for agents, state for graphs).
            chat_history: Chat conversation history (for agents only).

        Returns:
            Properly formatted input dictionary for the skill type.

        Raises:
            SkillValidationError: If input preparation fails validation.
        """
        if skill_metadata.skill_type == SkillType.AGENT:
            return SkillInputBuilder.prepare_agent_input(
                skill_metadata, task, context, chat_history
            )
        else:  # SkillType.GRAPH
            return SkillInputBuilder.prepare_graph_input(
                skill_metadata, task, context
            )

    @staticmethod
    def prepare_agent_input(
        skill_metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Prepare input for agent-type skills.

        Agent skills expect:
        - variables: Skill-specific variables from context
        - chat_history: Previous conversation messages
        - input: Current user request/task

        Args:
            skill_metadata: Metadata for the agent skill.
            task: User input/task for the agent.
            context: Variables to pass to the agent.
            chat_history: Conversation history.

        Returns:
            Agent input dictionary.

        Raises:
            SkillValidationError: If required inputs are missing or invalid.
        """
        logger.debug(f"Preparing agent input for skill: {skill_metadata.name}")

        if not task:
            raise SkillValidationError("Task is required for agent skills")

        # Validate chat_history format if provided
        if chat_history:
            SkillInputBuilder._validate_chat_history(chat_history)

        # Validate context variables against schema if defined
        variables = context or {}
        if skill_metadata.inputs.variables:
            variables = SkillInputBuilder._validate_agent_variables(
                variables, skill_metadata.inputs.variables
            )

        agent_input = {
            'variables': variables,
            'chat_history': chat_history or [],
            'input': task
        }

        logger.debug(f"Prepared agent input: variables={len(variables)}, "
                    f"chat_history={len(chat_history or [])}, task_length={len(task)}")

        return agent_input

    @staticmethod
    def prepare_graph_input(
        skill_metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare input for graph-type skills.

        Graph skills expect state variables with the task merged in
        as the 'input' field.

        Args:
            skill_metadata: Metadata for the graph skill.
            task: Task description to be included as 'input'.
            context: State variables for the graph.

        Returns:
            Graph state input dictionary.

        Raises:
            SkillValidationError: If required inputs are missing or invalid.
        """
        logger.debug(f"Preparing graph input for skill: {skill_metadata.name}")

        # Start with context (state variables)
        state_vars = context.copy() if context else {}

        # Add task as 'input' field (standard for graphs)
        state_vars['input'] = task

        # Validate state variables against schema if defined
        if skill_metadata.inputs.state_variables:
            state_vars = SkillInputBuilder._validate_graph_state_variables(
                state_vars, skill_metadata.inputs.state_variables
            )

        logger.debug(f"Prepared graph input: {len(state_vars)} state variables")

        return state_vars

    @staticmethod
    def _validate_chat_history(chat_history: List[Dict[str, str]]) -> None:
        """
        Validate chat history format.

        Args:
            chat_history: List of message dictionaries.

        Raises:
            SkillValidationError: If format is invalid.
        """
        if not isinstance(chat_history, list):
            raise SkillValidationError("chat_history must be a list")

        for i, message in enumerate(chat_history):
            if not isinstance(message, dict):
                raise SkillValidationError(f"chat_history[{i}] must be a dictionary")

            if 'role' not in message:
                raise SkillValidationError(f"chat_history[{i}] missing 'role' field")

            if 'content' not in message:
                raise SkillValidationError(f"chat_history[{i}] missing 'content' field")

            if message['role'] not in ['user', 'assistant', 'system']:
                logger.warning(f"Unusual role in chat_history[{i}]: {message['role']}")

    @staticmethod
    def _validate_agent_variables(
        variables: Dict[str, Any],
        variable_schema: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate agent variables against schema.

        Args:
            variables: Variables to validate.
            variable_schema: Schema definition for variables.

        Returns:
            Validated variables with defaults applied.

        Raises:
            SkillValidationError: If validation fails.
        """
        validated_vars = variables.copy()

        # Check for required variables and apply defaults
        for var_name, var_def in variable_schema.items():
            if var_name not in validated_vars:
                if 'default' in var_def:
                    validated_vars[var_name] = var_def['default']
                    logger.debug(f"Applied default for variable '{var_name}': {var_def['default']}")
                elif var_def.get('required', False):
                    raise SkillValidationError(f"Required variable '{var_name}' not provided")

            # Basic type validation (could be expanded)
            if var_name in validated_vars:
                expected_type = var_def.get('type')
                if expected_type:
                    SkillInputBuilder._validate_variable_type(
                        var_name, validated_vars[var_name], expected_type
                    )

        return validated_vars

    @staticmethod
    def _validate_graph_state_variables(
        state_vars: Dict[str, Any],
        state_schema: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate graph state variables against schema.

        Args:
            state_vars: State variables to validate.
            state_schema: Schema definition for state variables.

        Returns:
            Validated state variables with defaults applied.

        Raises:
            SkillValidationError: If validation fails.
        """
        validated_vars = state_vars.copy()

        # Check for required state variables and apply defaults
        for var_name, var_def in state_schema.items():
            if var_name not in validated_vars:
                if 'default' in var_def:
                    validated_vars[var_name] = var_def['default']
                    logger.debug(f"Applied default for state variable '{var_name}': {var_def['default']}")
                elif var_def.get('required', False):
                    raise SkillValidationError(f"Required state variable '{var_name}' not provided")

            # Basic type validation
            if var_name in validated_vars:
                expected_type = var_def.get('type')
                if expected_type:
                    SkillInputBuilder._validate_variable_type(
                        var_name, validated_vars[var_name], expected_type
                    )

        return validated_vars

    @staticmethod
    def _validate_variable_type(var_name: str, value: Any, expected_type: str) -> None:
        """
        Validate a variable against its expected type.

        Args:
            var_name: Name of the variable (for error messages).
            value: Value to validate.
            expected_type: Expected type string.

        Raises:
            SkillValidationError: If type validation fails.
        """
        # Simple type checking - could be made more sophisticated
        type_map = {
            'str': str,
            'string': str,
            'int': int,
            'integer': int,
            'float': float,
            'number': (int, float),
            'bool': bool,
            'boolean': bool,
            'dict': dict,
            'list': list
        }

        expected_python_type = type_map.get(expected_type.lower())
        if expected_python_type and not isinstance(value, expected_python_type):
            raise SkillValidationError(
                f"Variable '{var_name}' expected type {expected_type}, "
                f"got {type(value).__name__}"
            )

    @staticmethod
    def validate_skill_inputs(
        skill_metadata: SkillMetadata,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        Validate inputs for a skill without preparing them.

        This can be used to check if inputs are valid before execution.

        Args:
            skill_metadata: Metadata for the skill.
            task: Task to validate.
            context: Context data to validate.
            chat_history: Chat history to validate (for agents).

        Returns:
            List of validation error messages (empty if all valid).
        """
        errors = []

        try:
            SkillInputBuilder.prepare_input(
                skill_metadata, task, context, chat_history
            )
        except SkillValidationError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Unexpected validation error: {e}")

        return errors

    @staticmethod
    def get_input_schema_summary(skill_metadata: SkillMetadata) -> Dict[str, Any]:
        """
        Get a human-readable summary of the skill's input schema.

        Args:
            skill_metadata: Metadata for the skill.

        Returns:
            Dictionary summarizing the input requirements.
        """
        summary = {
            'skill_name': skill_metadata.name,
            'skill_type': skill_metadata.skill_type.value,
            'requires_task': True  # All skills require a task
        }

        if skill_metadata.skill_type == SkillType.AGENT:
            summary.update({
                'supports_chat_history': True,
                'variables': {}
            })

            if skill_metadata.inputs.variables:
                for var_name, var_def in skill_metadata.inputs.variables.items():
                    summary['variables'][var_name] = {
                        'type': var_def.get('type', 'any'),
                        'required': var_def.get('required', False),
                        'description': var_def.get('description', ''),
                        'default': var_def.get('default')
                    }

        else:  # GRAPH
            summary.update({
                'supports_chat_history': False,
                'state_variables': {}
            })

            if skill_metadata.inputs.state_variables:
                for var_name, var_def in skill_metadata.inputs.state_variables.items():
                    summary['state_variables'][var_name] = {
                        'type': var_def.get('type', 'any'),
                        'required': var_def.get('required', False),
                        'description': var_def.get('description', ''),
                        'default': var_def.get('default')
                    }

        return summary