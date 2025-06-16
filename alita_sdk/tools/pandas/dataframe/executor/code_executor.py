from typing import Any
from traceback import format_exc
from .code_environment import get_environment
from ..errors import CodeExecutionError, NoResultFoundError
            

class CodeExecutor:
    """
    Handle the logic on how to handle different lines of code
    """

    _environment: dict

    def __init__(self) -> None:
        self._environment = get_environment()

    def add_to_env(self, key: str, value: Any) -> None:
        """
        Expose extra variables in the code to be used
        Args:
            key (str): Name of variable or lib alias
            value (Any): It can any value int, float, function, class etc.
        """
        self._environment[key] = value

    def execute(self, code: str) -> dict:
        try:
            exec(code, self._environment)
        except Exception as e:
            raise CodeExecutionError(f"Code execution failed: {format_exc()}")
        return self._environment

    def execute_and_return_result(self, code: str) -> Any:
        """
        Executes the return updated environment
        """
        self.execute(code)

        # Get the result
        if "result" not in self._environment:
            raise NoResultFoundError("No result returned")

        return self._environment.get("result", None)

    @property
    def environment(self) -> dict:
        return self._environment