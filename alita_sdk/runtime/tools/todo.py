"""
To-Do toolkit for Alita SDK.
Provides task planning, progress tracking, and execution management capabilities.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Type, Any, List, Dict, Literal
from enum import Enum
from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field, create_model, ConfigDict, PrivateAttr

from ..clients import AlitaClient
from ...tools.base.tool import BaseAction
from ...tools.elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

name = "todo"


class SimpleStorage:
    """Simple in-memory storage that mimics memory_store interface."""

    def __init__(self):
        self._storage: Dict[tuple, Any] = {}

    def put(self, key: tuple, value: Any) -> None:
        """Store a value with the given key."""
        self._storage[key] = value

    def get(self, key: tuple) -> Optional[Any]:
        """Retrieve a value by key."""
        return self._storage.get(key)

    def list_keys(self, prefix: tuple = None) -> List[tuple]:
        """List all keys, optionally filtered by prefix."""
        if prefix is None:
            return list(self._storage.keys())
        return [k for k in self._storage.keys() if k[0] == prefix[0]]


class StorageAdapter:
    """
    Adapter to provide a unified interface for different storage backends.
    Handles differences between SimpleStorage and PostgresStore APIs.
    """

    def __init__(self, backend):
        self.backend = backend
        self._is_postgres = self._detect_postgres_store(backend)

    @staticmethod
    def _detect_postgres_store(backend) -> bool:
        """Detect if the backend is a PostgresStore based on its class name."""
        class_name = backend.__class__.__name__
        module_name = backend.__class__.__module__
        return 'PostgresStore' in class_name or 'postgres' in module_name.lower()

    @staticmethod
    def _serialize_for_storage(data: Any) -> Any:
        """
        Serialize data for storage, converting datetime objects to ISO strings.

        Args:
            data: Data to serialize (dict, list, or primitive)

        Returns:
            Serialized data safe for JSON storage
        """
        if isinstance(data, dict):
            return {key: StorageAdapter._serialize_for_storage(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [StorageAdapter._serialize_for_storage(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data

    @staticmethod
    def _deserialize_from_storage(data: Any) -> Any:
        """
        Deserialize data from storage, converting ISO strings back to datetime objects.

        Args:
            data: Data to deserialize

        Returns:
            Deserialized data with datetime objects restored
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Try to parse datetime strings
                if isinstance(value, str) and key.endswith('_at'):
                    try:
                        result[key] = datetime.fromisoformat(value)
                    except (ValueError, AttributeError):
                        result[key] = value
                else:
                    result[key] = StorageAdapter._deserialize_from_storage(value)
            return result
        elif isinstance(data, list):
            return [StorageAdapter._deserialize_from_storage(item) for item in data]
        return data

    def put(self, namespace: tuple, key: str, value: Any) -> None:
        """
        Store a value with unified interface.

        Args:
            namespace: Tuple representing the namespace (e.g., ("todo_plans",))
            key: String key within the namespace
            value: Value to store
        """
        # Serialize the value to handle datetime objects
        serialized_value = self._serialize_for_storage(value)

        if self._is_postgres:
            # PostgresStore API: put(namespace, key, value)
            self.backend.put(namespace=namespace, key=key, value=serialized_value)
        else:
            # SimpleStorage API: put((namespace, key), value)
            combined_key = namespace + (key,)
            self.backend.put(combined_key, serialized_value)

    def get(self, namespace: tuple, key: str) -> Optional[Any]:
        """
        Retrieve a value with unified interface.

        Args:
            namespace: Tuple representing the namespace
            key: String key within the namespace

        Returns:
            Retrieved value or None if not found
        """
        if self._is_postgres:
            # PostgresStore API: get(namespace, key)
            result = self.backend.get(namespace=namespace, key=key)
            if result:
                # PostgresStore returns an Item object with a 'value' attribute
                value = result.value if hasattr(result, 'value') else result
            else:
                value = None
        else:
            # SimpleStorage API: get((namespace, key))
            combined_key = namespace + (key,)
            value = self.backend.get(combined_key)

        # Deserialize the value to restore datetime objects
        if value:
            return self._deserialize_from_storage(value)
        return None

    def list_keys(self, namespace: tuple) -> List[str]:
        """
        List all keys in a namespace with unified interface.

        Args:
            namespace: Tuple representing the namespace

        Returns:
            List of keys in the namespace
        """
        if self._is_postgres:
            # PostgresStore API: search(namespace_prefix)
            try:
                items = self.backend.search(namespace)
                return [item.key for item in items]
            except Exception as e:
                logger.warning(f"Error listing keys from PostgresStore: {e}")
                return []
        else:
            # SimpleStorage API: list_keys(prefix)
            keys = self.backend.list_keys(prefix=namespace)
            # Extract just the key portion (last element of tuple)
            return [k[-1] for k in keys if len(k) > len(namespace)]


class TaskStatus(str, Enum):
    """Task status enumeration."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        # This will help Pydantic v2 generate the schema
        return {
            "type": "string",
            "enum": [e.value for e in cls]
        }


class Task(BaseModel):
    """Individual task model."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task identifier")
    title: str = Field(description="Task title")
    description: Optional[str] = Field(default=None, description="Task description")
    status: Literal["todo", "in_progress", "completed", "cancelled"] = Field(default="todo", description="Task status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")


class TodoPlan(BaseModel):
    """Todo plan model containing multiple tasks."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique plan identifier")
    title: str = Field(description="Plan title")
    description: Optional[str] = Field(default=None, description="Plan description")
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


# Input schemas for tools
class CreatePlanInput(BaseModel):
    """Input schema for creating a new todo plan."""
    title: str = Field(description="Title of the todo plan")
    description: Optional[str] = Field(default=None, description="Description of the todo plan")
    tasks: List[str] = Field(description="List of task titles to include in the plan")


class AddTaskInput(BaseModel):
    """Input schema for adding a task to a plan."""
    plan_id: str = Field(description="ID of the plan to add the task to")
    title: str = Field(description="Title of the task")
    description: Optional[str] = Field(default=None, description="Description of the task")


class UpdateTaskStatusInput(BaseModel):
    """Input schema for updating task status."""
    plan_id: str = Field(description="ID of the plan containing the task")
    task_id: str = Field(description="ID of the task to update")
    status: Literal["todo", "in_progress", "completed", "cancelled"] = Field(description="New status for the task")


class GetTaskStatusInput(BaseModel):
    """Input schema for getting task status."""
    plan_id: str = Field(description="ID of the plan containing the task")
    task_id: str = Field(description="ID of the task to get status for")


class GetPlanStatusInput(BaseModel):
    """Input schema for getting plan status."""
    plan_id: str = Field(description="ID of the plan to get status for")


class ListPlansInput(BaseModel):
    """Input schema for listing all plans."""
    pass


class TodoApiWrapper(BaseToolApiWrapper):
    """
    Wrapper for Todo management operations.
    Similar to JiraApiWrapper, this class manages the shared memory store and provides
    all tool methods.
    """

    memory_store: Optional[Any] = None
    _storage: Any = PrivateAttr()
    _namespace: tuple = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)

        try:
            if not self.memory_store:
                from ...runtime.langchain.store_manager import get_manager
                alita_client = data.get('alita_client', None)
                if alita_client:
                    conn_str = alita_client.unsecret('pgvector_project_connstr')
                    self.memory_store = get_manager().get_store(conn_str)
        except Exception as e:
            logger.warning(f"Could not initialize memory_store from store_manager: {e}")

        # Initialize storage - use provided memory_store or create SimpleStorage
        if self.memory_store is None:
            backend = SimpleStorage()
        else:
            backend = self.memory_store

        # Wrap the backend with StorageAdapter for unified interface
        self._storage = StorageAdapter(backend)
        self._namespace = (f"todo_plans_{data.get('toolkit_id', '')}",)

    def create_plan(self, title: str, tasks: List[str], description: Optional[str] = None) -> str:
        """Create a new todo plan with tasks."""
        try:
            # Create tasks from the task titles
            task_objects = [
                Task(title=task_title, description=f"Task: {task_title}")
                for task_title in tasks
            ]

            # Create the plan
            plan = TodoPlan(
                title=title,
                description=description,
                tasks=task_objects
            )

            # Store in memory using StorageAdapter
            self._storage.put(
                namespace=self._namespace,
                key=plan.id,
                value={"plan": plan.model_dump()}
            )

            return (f"Done. Created todo plan '{title}' with {len(tasks)} tasks. "
                    f"Plan ID: {plan.id}. Tasks: {[{'id': task.id, 'title': task.title, 'status': task.status} for task in plan.tasks]}")

        except Exception as e:
            logger.error(f"Error creating todo plan: {e}")
            return f"Error creating todo plan: {str(e)}"

    def add_task(self, plan_id: str, title: str, description: Optional[str] = None) -> str:
        """Add a new task to an existing plan."""
        try:
            # Retrieve the plan using StorageAdapter
            plan_data = self._storage.get(namespace=self._namespace, key=plan_id)
            if not plan_data:
                return f"Error: No plan found with ID: {plan_id}"

            plan = TodoPlan(**plan_data["plan"])

            # Create new task
            new_task = Task(title=title, description=description)
            plan.tasks.append(new_task)
            plan.updated_at = datetime.now()

            # Update stored plan
            self._storage.put(
                namespace=self._namespace,
                key=plan_id,
                value={"plan": plan.model_dump()}
            )

            return (f"Done. Added task '{title}' (ID: {new_task.id}) to plan '{plan.title}'. "
                    f"Total tasks: {len(plan.tasks)}")

        except Exception as e:
            logger.error(f"Error adding task to plan: {e}")
            return f"Error adding task: {str(e)}"

    def update_task_status(self, plan_id: str, task_id: str,
                           status: Literal["todo", "in_progress", "completed", "cancelled"]) -> str:
        """Update the status of a task in a todo plan.
        Args:
            plan_id: ID of the plan containing the task
            task_id: ID of the task to update
            status: New status for the task
        """
        try:
            # Retrieve the plan
            plan_data = self._storage.get(namespace=self._namespace, key=plan_id)
            if not plan_data:
                return f"Error: No plan found with ID: {plan_id}"

            plan = TodoPlan(**plan_data["plan"])

            # Find and update the task
            task_found = False
            for task in plan.tasks:
                if task.id == task_id:
                    old_status = task.status
                    task.status = status
                    task.updated_at = datetime.now()
                    if status == TaskStatus.COMPLETED.value:
                        task.completed_at = datetime.now()
                    task_found = True
                    break

            if not task_found:
                return f"Error: No task found with ID: {task_id} in plan {plan_id}"

            plan.updated_at = datetime.now()

            # Update stored plan
            self._storage.put(
                namespace=self._namespace,
                key=plan_id,
                value={"plan": plan.model_dump()}
            )

            return f"Done. Updated task '{task.title}' status from '{old_status}' to '{status}'"

        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return f"Error updating task status: {str(e)}"

    def get_task_status(self, plan_id: str, task_id: str) -> str:
        """
            Get the current status of a specific task.
            NOTE: This method retrieves task details including status, timestamps, etc.
            If plan id is not provided, it searches all plans for the task id.
        Args:
            plan_id: ID of the plan containing the task
            task_id: ID of the task to get status for

        """
        try:
            # Retrieve the plan
            plan_data = self._storage.get(namespace=self._namespace, key=plan_id)
            if not plan_data:
                return f"Error: No plan found with ID: {plan_id}"

            plan = TodoPlan(**plan_data["plan"])

            # Find the task
            for task in plan.tasks:
                if task.id == task_id:
                    task_info = {
                        "task_id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "status": task.status,
                        "created_at": task.created_at,
                        "updated_at": task.updated_at,
                        "completed_at": task.completed_at
                    }
                    return f"Task details: {task_info}"

            return f"Error: No task found with ID: {task_id} in plan {plan_id}"

        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return f"Error getting task status: {str(e)}"

    def get_plan_status(self, plan_id: str) -> str:
        """Get the current status and progress of a todo plan."""
        try:
            # Retrieve the plan
            plan_data = self._storage.get(namespace=self._namespace, key=plan_id)
            if not plan_data:
                return f"Error: No plan found with ID: {plan_id}"

            plan = TodoPlan(**plan_data["plan"])

            # Calculate progress statistics
            total_tasks = len(plan.tasks)
            completed_tasks = len([task for task in plan.tasks if task.status == TaskStatus.COMPLETED.value])
            in_progress_tasks = len([task for task in plan.tasks if task.status == TaskStatus.IN_PROGRESS.value])
            todo_tasks = len([task for task in plan.tasks if task.status == TaskStatus.TODO.value])
            cancelled_tasks = len([task for task in plan.tasks if task.status == TaskStatus.CANCELLED.value])

            progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

            # Organize tasks by status
            tasks_by_status = {
                "completed": [{"id": task.id, "title": task.title, "completed_at": task.completed_at}
                              for task in plan.tasks if task.status == TaskStatus.COMPLETED.value],
                "in_progress": [{"id": task.id, "title": task.title, "updated_at": task.updated_at}
                                for task in plan.tasks if task.status == TaskStatus.IN_PROGRESS.value],
                "todo": [{"id": task.id, "title": task.title}
                         for task in plan.tasks if task.status == TaskStatus.TODO.value],
                "cancelled": [{"id": task.id, "title": task.title}
                              for task in plan.tasks if task.status == TaskStatus.CANCELLED.value]
            }

            status_info = {
                "plan_id": plan_id,
                "plan_title": plan.title,
                "plan_description": plan.description,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "todo_tasks": todo_tasks,
                "cancelled_tasks": cancelled_tasks,
                "progress_percentage": round(progress_percentage, 1),
                "tasks_by_status": tasks_by_status,
                "created_at": plan.created_at,
                "updated_at": plan.updated_at
            }

            return f"Plan status: {status_info}"

        except Exception as e:
            logger.error(f"Error getting plan status: {e}")
            return f"Error getting plan status: {str(e)}"

    def list_plans(self) -> str:
        """List all todo plans with their basic information and progress.
        Can be used to search required plan with a task.
        """
        try:
            # Get all plan keys
            plans_summary = []
            plan_keys = self._storage.list_keys(namespace=self._namespace)
            for key in plan_keys:
                try:
                    plan_data = self._storage.get(self._namespace, key)
                    if plan_data and "plan" in plan_data:
                        plan = TodoPlan(**plan_data["plan"])

                        # Calculate progress
                        total_tasks = len(plan.tasks)
                        completed_tasks = len(
                            [task for task in plan.tasks if task.status == TaskStatus.COMPLETED.value])
                        progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

                        plans_summary.append({
                            "plan_id": plan.id,
                            "title": plan.title,
                            "description": plan.description,
                            "total_tasks": total_tasks,
                            "completed_tasks": completed_tasks,
                            "progress_percentage": round(progress_percentage, 1),
                            "created_at": plan.created_at,
                            "updated_at": plan.updated_at
                        })
                except Exception as e:
                    logger.warning(f"Error processing plan with key {key}: {e}")
                    continue

            return f"Found {len(plans_summary)} todo plan(s): {plans_summary}"

        except Exception as e:
            logger.error(f"Error listing plans: {e}")
            return f"Error listing plans: {str(e)}"

    def get_available_tools(self):
        """Get list of available tools with their configurations."""
        return [
            {
                "name": "create_todo_plan",
                "description": self.create_plan.__doc__,
                "args_schema": CreatePlanInput,
                "ref": self.create_plan,
            },
            {
                "name": "add_task_to_plan",
                "description": self.add_task.__doc__,
                "args_schema": AddTaskInput,
                "ref": self.add_task,
            },
            {
                "name": "update_task_status",
                "description": self.update_task_status.__doc__,
                "args_schema": UpdateTaskStatusInput,
                "ref": self.update_task_status,
            },
            {
                "name": "get_task_status",
                "description": self.get_task_status.__doc__,
                "args_schema": GetTaskStatusInput,
                "ref": self.get_task_status,
            },
            {
                "name": "get_plan_status",
                "description": self.get_plan_status.__doc__,
                "args_schema": GetPlanStatusInput,
                "ref": self.get_plan_status,
            },
            {
                "name": "list_todo_plans",
                "description": self.list_plans.__doc__,
                "args_schema": ListPlansInput,
                "ref": self.list_plans,
            },
        ]


class TodoToolkit(BaseToolkit):
    """Toolkit for todo management tools."""
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> Type[BaseModel]:
        """Get the configuration schema for the todo toolkit."""
        # Create a wrapper instance to get tool schemas
        wrapper = TodoApiWrapper()
        available_tools = wrapper.get_available_tools()
        selected_tools = {tool["name"]: tool["args_schema"].model_json_schema() for tool in available_tools}

        return create_model(
            'todo',
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Todo Management",
                    "icon_url": "todo.svg",
                    "hidden": True,
                    "categories": ["planning", "internal_tool"],
                    "extra_categories": ["todo", "task management", "planning", "progress tracking"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, memory_store=None, alita_client: Optional[AlitaClient] = None, toolkit_id: Optional[str | int] = None, **kwargs):
        """
        Get toolkit with todo management tools.

        Args:
            memory_store: Memory store for persistence (optional, will use SimpleStorage if not provided)
            toolkit_id: Optional toolkit identifier
            **kwargs: Additional arguments
        """
        # Create the wrapper with a shared memory store
        wrapper = TodoApiWrapper(memory_store=memory_store, alita_client=alita_client, toolkit_id=toolkit_id)

        # Get available tools from wrapper
        available_tools = wrapper.get_available_tools()

        # Create BaseTool instances from the wrapper methods
        tools = []
        for tool_config in available_tools:
            tools.append(BaseAction(
                api_wrapper=wrapper,
                name=tool_config["name"],
                description=tool_config['description'],
                args_schema=tool_config["args_schema"]
            ))

        return cls(tools=tools)

    def get_tools(self):
        return self.tools


def get_tools(tools_list: list, alita_client=None, llm=None, memory_store=None):
    """
    Get todo tools for the provided tool configurations.

    Args:
        tools_list: List of tool configurations
        alita_client: Alita client instance (unused for todo)
        llm: LLM client instance (unused for todo)
        memory_store: Optional memory store instance (used for persistence)

    Returns:
        List of todo tools
    """
    all_tools = []

    for tool in tools_list:
        if tool.get('type') == 'todo' or tool.get('toolkit_name') == 'todo':
            try:
                toolkit_instance = TodoToolkit.get_toolkit(
                    memory_store=memory_store,
                    toolkit_name=tool.get('toolkit_name', '')
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                logger.error(f"Error in todo toolkit get_tools: {e}")
                logger.error(f"Tool config: {tool}")
                raise

    return all_tools


def create_todo_tools(memory_store=None):
    """Create todo management tools with optional memory store."""
    return TodoToolkit.get_toolkit(memory_store=memory_store).get_tools()
