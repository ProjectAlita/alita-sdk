import asyncio
import logging
import subprocess
import os
from typing import Any, Type, Optional, Dict, List, Literal, Union
from copy import deepcopy
from pathlib import Path

from langchain_core.tools import BaseTool, BaseToolkit
from langchain_core.messages import ToolCall
from pydantic import BaseModel, create_model, ConfigDict, Field
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)

name = "pyodide"


def get_tools(tools_list: list, alita_client=None, llm=None, memory_store=None):
    """
    Get sandbox tools for the provided tool configurations.

    Args:
        tools_list: List of tool configurations
        alita_client: Alita client instance for sandbox tools
        llm: LLM client instance (unused for sandbox)
        memory_store: Optional memory store instance (unused for sandbox)

    Returns:
        List of sandbox tools
    """
    all_tools = []

    for tool in tools_list:
        if tool.get('type') == 'sandbox' or tool.get('toolkit_name') == 'sandbox':
            try:
                toolkit_instance = SandboxToolkit.get_toolkit(
                    stateful=tool['settings'].get('stateful', False),
                    allow_net=tool['settings'].get('allow_net', True),
                    alita_client=alita_client,
                    toolkit_name=tool.get('toolkit_name', '')
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                logger.error(f"Error in sandbox toolkit get_tools: {e}")
                logger.error(f"Tool config: {tool}")
                raise

    return all_tools


def _is_deno_available() -> bool:
    """Check if Deno is available in the PATH"""
    try:
        result = subprocess.run(
            ["deno", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def _setup_pyodide_cache_env() -> None:
    """Setup Pyodide caching environment variables for performance optimization [NO-OP]"""
    try:
        for key in ["SANDBOX_BASE", "DENO_DIR"]:
            logger.info("Sandbox env: %s -> %s", key, os.environ.get(key, "n/a"))
    except Exception as e:
        logger.warning(f"Could not setup Pyodide cache environment: {e}")


# Create input schema for the sandbox tool
sandbox_tool_input = create_model(
    "SandboxToolInput",
    code=(str, FieldInfo(description="Python code to execute in the sandbox environment"))
)


class PyodideSandboxTool(BaseTool):
    """
    A tool that provides secure Python code execution using Pyodide (Python compiled to WebAssembly).
    This tool leverages langchain-sandbox to provide a safe environment for running untrusted Python code.
    Optimized for performance with caching and stateless execution by default.
    """

    name: str = "pyodide_sandbox"
    description: str = """Execute Python code in a secure sandbox environment using Pyodide.
    This tool allows safe execution of Python code without access to the host system.
    Use this tool when you need to:
    - Execute Python code snippets
    - Perform calculations or data analysis
    - Test Python algorithms
    - Run code that requires isolation from the host system

    The sandbox supports most Python standard library modules and can install additional packages.
    Note: File access and some system operations are restricted for security.
    Optimized for performance with local caching (stateless by default for faster execution).
    """
    args_schema: Type[BaseModel] = sandbox_tool_input
    stateful: bool = False  # Default to stateless for better performance
    allow_net: bool = True
    session_bytes: Optional[bytes] = None
    session_metadata: Optional[Dict] = None
    alita_client: Optional[Any] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sandbox = None
        # Setup caching environment for optimal performance
        _setup_pyodide_cache_env()
        self._initialize_sandbox()

    def _prepare_pyodide_input(self, code: str) -> str:
        """Prepare input for PyodideSandboxTool by injecting state and alita_client into the code block."""
        pyodide_predata = ""

        # Add alita_client if available
        if self.alita_client:
            try:
                # Get the directory of the current file and construct the path to sandbox_client.py
                current_dir = Path(__file__).parent
                sandbox_client_path = current_dir.parent / 'clients' / 'sandbox_client.py'

                with open(sandbox_client_path, 'r') as f:
                    sandbox_client_code = f.read()
                pyodide_predata += f"{sandbox_client_code}\n"
                pyodide_predata += (f"alita_client = SandboxClient(base_url='{self.alita_client.base_url}',"
                                    f"project_id={self.alita_client.project_id},"
                                    f"auth_token='{self.alita_client.auth_token}')\n")
            except FileNotFoundError:
                logger.error(f"sandbox_client.py not found. Ensure the file exists.")

        return f"#elitea simplified client\n{pyodide_predata}{code}"

    def _initialize_sandbox(self) -> None:
        """Initialize the PyodideSandbox instance with optimized settings"""
        try:
            # Check if Deno is available
            if not _is_deno_available():
                error_msg = (
                    "Deno is required for PyodideSandbox but is not installed. "
                    "Please run the bootstrap.sh script or install Deno manually."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            from langchain_sandbox import PyodideSandbox

            # Air-gapped settings
            sandbox_base = os.environ.get("SANDBOX_BASE", os.path.expanduser('~/.cache/pyodide'))
            sandbox_tmp = os.path.join(sandbox_base, "tmp")
            deno_cache = os.environ.get("DENO_DIR", os.path.expanduser('~/.cache/deno'))

            # Configure sandbox with performance optimizations
            self._sandbox = PyodideSandbox(
                stateful=self.stateful,
                #
                allow_env=["SANDBOX_BASE"],
                allow_read=[sandbox_base, sandbox_tmp, deno_cache],
                allow_write=[sandbox_tmp, deno_cache],
                #
                allow_net=self.allow_net,
                # Use auto node_modules_dir for better caching
                node_modules_dir="auto"
            )
            logger.info(f"PyodideSandbox initialized successfully (stateful={self.stateful})")
        except ImportError as e:
            if "langchain_sandbox" in str(e):
                error_msg = (
                    "langchain-sandbox is required for the PyodideSandboxTool. "
                    "Please install it with: pip install langchain-sandbox"
                )
                logger.error(error_msg)
                raise ImportError(error_msg) from e
            else:
                logger.error(f"Failed to import required module: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to initialize PyodideSandbox: {e}")
            raise

    def _run(self, code: str) -> str:
        """
        Synchronous version - runs the async method in a new event loop
        """
        try:
            # Check if sandbox is initialized, if not try to initialize
            if self._sandbox is None:
                self._initialize_sandbox()

            # Prepare code with state and client injection
            prepared_code = self._prepare_pyodide_input(code)

            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, but _run is supposed to be sync
                # We'll need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._arun(prepared_code))
                    return future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(self._arun(prepared_code))
        except (ImportError, RuntimeError) as e:
            # Handle specific dependency errors gracefully
            error_msg = str(e)
            if "langchain-sandbox" in error_msg:
                return "❌ PyodideSandboxTool requires langchain-sandbox. Install with: pip install langchain-sandbox"
            elif "Deno" in error_msg:
                return "❌ PyodideSandboxTool requires Deno. Install from: https://docs.deno.com/runtime/getting_started/installation/"
            else:
                return f"❌ PyodideSandboxTool initialization failed: {error_msg}"
        except Exception as e:
            logger.error(f"Error executing code in sandbox: {e}")
            return f"Error executing code: {str(e)}"

    async def _arun(self, code: str) -> str:
        """
        Execute Python code in the Pyodide sandbox
        """
        try:
            if self._sandbox is None:
                self._initialize_sandbox()

            # Execute the code with session state if available
            result = await self._sandbox.execute(
                code,
                session_bytes=self.session_bytes,
                session_metadata=self.session_metadata
            )

            # Update session state for stateful execution
            if self.stateful:
                self.session_bytes = result.session_bytes
                self.session_metadata = result.session_metadata

            result_dict = {}

            if result.result is not None:
                result_dict["result"] = result.result

            if result.stdout:
                result_dict["output"] = result.stdout

            if result.stderr:
                result_dict["error"] = result.stderr

            if result.status == 'error':
                result_dict["status"] = "Execution failed"

            execution_info = f"Execution time: {result.execution_time:.2f}s"
            if result.session_metadata and 'packages' in result.session_metadata:
                packages = result.session_metadata.get('packages', [])
                if packages:
                    execution_info += f", Packages: {', '.join(packages)}"

            result_dict["execution_info"] = execution_info
            return result_dict

        except Exception as e:
            logger.error(f"Error executing code in sandbox: {e}")
            return {"error": f"Error executing code: {str(e)}"}


class StatefulPyodideSandboxTool(PyodideSandboxTool):
    """
    A stateful version of the PyodideSandboxTool that maintains state between executions.
    This version preserves variables, imports, and function definitions across multiple tool calls.
    """

    name: str = "stateful_pyodide_sandbox"
    description: str = """Execute Python code in a stateful sandbox environment using Pyodide.
    This tool maintains state between executions, preserving variables, imports, and function definitions.
    Use this tool when you need to:
    - Build upon previous code executions
    - Maintain variables across multiple calls
    - Develop complex programs step by step
    - Preserve imported libraries and defined functions

    The sandbox supports most Python standard library modules and can install additional packages.
    Note: File access and some system operations are restricted for security.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs['stateful'] = True  # Force stateful mode
        super().__init__(**kwargs)


# Factory function for creating sandbox tools
def create_sandbox_tool(stateful: bool = False, allow_net: bool = True, alita_client: Optional[Any] = None) -> BaseTool:
    """
    Factory function to create sandbox tools with specified configuration.

    Note: This tool requires Deno to be installed and available in PATH.
    For installation and optimization, run the bootstrap.sh script.

    Args:
        stateful: Whether to maintain state between executions (default: False for better performance)
        allow_net: Whether to allow network access (for package installation)

    Returns:
        Configured sandbox tool instance

    Raises:
        ImportError: If langchain-sandbox is not installed
        RuntimeError: If Deno is not found in PATH

    Performance Notes:
        - Stateless mode (default) is faster and avoids session state overhead
        - Run bootstrap.sh script to enable local caching and reduce initialization time
        - Cached wheels reduce package download time from ~4.76s to near-instant
    """
    if stateful:
        return StatefulPyodideSandboxTool(allow_net=allow_net, alita_client=alita_client)
    else:
        return PyodideSandboxTool(stateful=False, allow_net=allow_net, alita_client=alita_client)


class SandboxToolkit(BaseToolkit):
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> Type[BaseModel]:
        # Create sample tools to get their schemas
        sample_tools = [
            PyodideSandboxTool(),
            StatefulPyodideSandboxTool()
        ]
        selected_tools = {x.name: x.args_schema.model_json_schema() for x in sample_tools}

        return create_model(
            'sandbox',
            stateful=(bool, Field(default=False, description="Whether to maintain state between executions")),
            allow_net=(bool, Field(default=True, description="Whether to allow network access for package installation")),
            selected_tools=(List[Literal[tuple(selected_tools)]],
                            Field(default=[], json_schema_extra={'args_schemas': selected_tools})),

            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Python Sandbox",
                    "icon_url": "sandbox.svg",
                    "hidden": False,
                    "categories": ["code", "execution", "internal_tool"],
                    "extra_categories": ["python", "pyodide", "sandbox", "code execution"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, stateful: bool = False, allow_net: bool = True, alita_client=None, **kwargs):
        """
        Get toolkit with sandbox tools.

        Args:
            stateful: Whether to maintain state between executions
            allow_net: Whether to allow network access
            alita_client: Alita client instance for sandbox tools
            **kwargs: Additional arguments
        """
        tools = []

        if stateful:
            tools.append(StatefulPyodideSandboxTool(allow_net=allow_net, alita_client=alita_client))
        else:
            tools.append(PyodideSandboxTool(stateful=False, allow_net=allow_net, alita_client=alita_client))

        return cls(tools=tools)

    def get_tools(self):
        return self.tools
