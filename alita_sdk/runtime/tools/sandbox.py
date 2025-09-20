import logging
import asyncio
import subprocess
import os
from typing import Any, Type, Optional, Union, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


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
    """Setup Pyodide caching environment variables for performance optimization"""
    try:
        # Check if cache environment file exists and source it
        cache_env_file = os.path.expanduser("~/.pyodide_cache_env")
        if os.path.exists(cache_env_file):
            with open(cache_env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export ') and '=' in line:
                        # Parse export VAR=value format
                        var_assignment = line[7:]  # Remove 'export '
                        if '=' in var_assignment:
                            key, value = var_assignment.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"').strip("'")
                            os.environ[key] = value
                            logger.debug(f"Set Pyodide cache env: {key}={value}")
        
        # Set default caching environment variables if not already set
        cache_defaults = {
            'PYODIDE_PACKAGES_PATH': os.path.expanduser('~/.cache/pyodide'),
            'DENO_DIR': os.path.expanduser('~/.cache/deno'),
            'PYODIDE_CACHE_DIR': os.path.expanduser('~/.cache/pyodide'),
        }
        
        for key, default_value in cache_defaults.items():
            if key not in os.environ:
                os.environ[key] = default_value
                logger.debug(f"Set default Pyodide env: {key}={default_value}")
                
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
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sandbox = None
        # Setup caching environment for optimal performance
        _setup_pyodide_cache_env()
        self._initialize_sandbox()
    
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
            
            # Configure sandbox with performance optimizations
            self._sandbox = PyodideSandbox(
                stateful=self.stateful,
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
            
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, but _run is supposed to be sync
                # We'll need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._arun(code))
                    return future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(self._arun(code))
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
            
            # Format the output
            output_parts = []
            
            if result.result is not None:
                output_parts.append(f"Result: {result.result}")
            
            if result.stdout:
                output_parts.append(f"Output: {result.stdout}")
            
            if result.stderr:
                output_parts.append(f"Error: {result.stderr}")
            
            if result.status == 'error':
                output_parts.append(f"Execution failed with status: {result.status}")
            
            execution_info = f"Execution time: {result.execution_time:.2f}s"
            if result.session_metadata and 'packages' in result.session_metadata:
                packages = result.session_metadata.get('packages', [])
                if packages:
                    execution_info += f", Packages: {', '.join(packages)}"
            
            output_parts.append(execution_info)
            
            return "\n".join(output_parts) if output_parts else "Code executed successfully (no output)"
            
        except Exception as e:
            logger.error(f"Error executing code in sandbox: {e}")
            return f"Error executing code: {str(e)}"


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
def create_sandbox_tool(stateful: bool = False, allow_net: bool = True) -> BaseTool:
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
        return StatefulPyodideSandboxTool(allow_net=allow_net)
    else:
        return PyodideSandboxTool(stateful=False, allow_net=allow_net)