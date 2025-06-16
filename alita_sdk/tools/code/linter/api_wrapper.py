import logging
import subprocess
from typing import Tuple, Dict, List, Optional, Any

from pydantic import model_validator, create_model, Field, PrivateAttr

from ...elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

class PythonLinter(BaseToolApiWrapper):
    error_codes: str
    _client: Optional['PythonLinter'] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        error_codes = values.get('error_codes')
        cls._client = cls(error_codes=error_codes)
        return values

    def lint_code_diff(self, old_content: str, new_content: str) -> Tuple[bool, str]:
        """Lint the given code content."""
        errors = self.lint_single_code(new_content)

        if not errors:
            return True, ""

        changed_lines = self.get_changed_lines(old_content, new_content)
        new_errors = self._filter_new_errors(errors, changed_lines)

        if not new_errors:
            return True, ""

        error_message = self._format_errors(new_errors)
        return False, error_message

    def lint_single_code(self, content: str) -> Dict[int, str]:
        try:
            error_lines = self._run_flake8_cli(content, self.error_codes)
        except subprocess.SubprocessError as e:
            logger.error(f"An error occurred while running flake8: {e}")
            return {}

        error_dict = {}
        for error in error_lines:
            parts = error.split(":")
            if len(parts) > 1:
                try:
                    line_number = int(parts[1])
                    error_dict[line_number] = error
                except ValueError:
                    logger.error(f"Could not parse line number from error: {error}")

        return error_dict

    @staticmethod
    def _run_flake8_cli(content: str, error_codes: str):
        res_cli = subprocess.run(
            ["flake8", "--select", error_codes, "-"],
            input=content,
            text=True,
            capture_output=True,
            check=False
        )
        return res_cli.stdout.splitlines()

    @staticmethod
    def _filter_new_errors(errors: Dict[int, str], changed_lines: Dict[int, str]) -> List[Tuple[str, str]]:
        retained_errors = []

        for line_number, error_detail in errors.items():
            if line_number in changed_lines:
                line_content = changed_lines[line_number]
                retained_errors.append((line_content, error_detail))

        return retained_errors

    @staticmethod
    def _format_errors(errors: List[Tuple[str, str]]) -> str:
        formatted_errors = []
        for line_content, error_details in errors:
            formatted_errors.append(f"Line: {line_content}\nError: {error_details}\n")
        return "\n".join(formatted_errors)

    @staticmethod
    def get_changed_lines(old_content: str, new_content: str) -> Dict[int, str]:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        max_lines = max(len(old_lines), len(new_lines))

        changed_lines = {
            i + 1: new_lines[i] if i < len(new_lines) else ""
            for i in range(max_lines)
            if (i < len(old_lines) and old_lines[i] != new_lines[i]) or (i >= len(old_lines))
        }

        return changed_lines

    def get_available_tools(self):
        return [
            {
                "name": "lint_code_diff",
                "ref": self.lint_code_diff,
                "description": self.lint_code_diff.__doc__,
                "args_schema": create_model(
                    "LintCodeDiffModel",
                    old_content=(str, Field(description="The original content of the code")),
                    new_content=(str, Field(description="The new content of the code to be linted"))
                ),
            }
        ]