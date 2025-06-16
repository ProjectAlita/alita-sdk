import ast
import os.path
import re
import uuid
from pathlib import Path
from pandas import DataFrame

import astor

from ..prompts import DEFAULT_CHART_DIRECTORY


class CodeCleaner:
    def __init__(self, df: DataFrame):
        """
        Initialize the CodeCleaner with the provided context.

        Args:
            context (AgentState): The pipeline context for cleaning and validation.
        """
        self._df = df


    def get_target_names(self, targets):
        target_names = []
        is_slice = False

        for target in targets:
            if isinstance(target, ast.Name) or (
                isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
            ):
                target_names.append(
                    target.id if isinstance(target, ast.Name) else target.value.id
                )
                is_slice = isinstance(target, ast.Subscript)

        return target_names, is_slice, target

    def check_is_df_declaration(self, node: ast.AST):
        value = node.value
        return (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and hasattr(value.func.value, "id")
            and value.func.value.id == "pd"
            and value.func.attr == "DataFrame"
        )

    def clean_code(self, code: str) -> str:
        """
        Clean the provided code by validating imports, handling SQL queries, and processing charts.

        Args:
            code (str): The code to clean.

        Returns:
            tuple: Cleaned code as a string and a list of additional dependencies.
        """
        code = self._replace_output_filenames_with_temp_chart(code)

        # If plt.show is in the code, remove that line
        code = re.sub(r"plt.show\(\)", "", code)

        tree = ast.parse(code)
        new_body = []

        for node in tree.body:
            new_body.append(node)

        new_tree = ast.Module(body=new_body)
        return astor.to_source(new_tree, pretty_source=lambda x: "".join(x)).strip()

    def _replace_output_filenames_with_temp_chart(self, code: str) -> str:
        """
        Replace output file names with "temp_chart.png".
        """
        _id = uuid.uuid4()
        chart_path = os.path.join(DEFAULT_CHART_DIRECTORY, f"temp_chart_{_id}.png")
        chart_path = chart_path.replace("\\", "\\\\")
        return re.sub(
            r"""(['"])([^'"]*\.png)\1""",
            lambda m: f"{m.group(1)}{chart_path}{m.group(1)}",
            code,
        )