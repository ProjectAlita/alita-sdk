from typing import Any
import traceback
import logging
from pandas import DataFrame
from ..prompts import PLAN_CODE_PROMPT
from ...statsmodels import prompt_addon
from .code_cleaning import CodeCleaner
from .code_validator import CodeRequirementValidator

logger = logging.getLogger(__name__)

class CodeGenerator:
    def __init__(self, df: DataFrame, df_description: str, llm: Any):
        self.llm = llm
        self._df_description = df_description
        self._code_cleaner = CodeCleaner(df=df)
        self._code_validator = CodeRequirementValidator()

    def generate_code(self, prompt: str, error_trace:str = None) -> str:
        """
        Generates code using a given LLM and performs validation and cleaning steps.

        Args:
            context (PipelineContext): The pipeline context containing dataframes and logger.
            prompt (BasePrompt): The prompt to guide code generation.

        Returns:
            str: The final cleaned and validated code.

        Raises:
            Exception: If any step fails during the process.
        """
        try:
            logger.debug(f"Using Prompt: {prompt}")
            prompt = PLAN_CODE_PROMPT.format(dataframe=self._df_description, task=prompt, prompt_addon=prompt_addon)
            if error_trace:
                prompt += f"\n Last time you failed to generate the code <ErrorTrace>{error_trace}</ErrorTrace>"
            messages = [
                {"role": "user",  "content": [{"type": "text", "text": prompt}]}
            ]
            # Generate the code
            code = self.llm.invoke(messages).content
            return self.validate_and_clean_code(code)

        except Exception as e:
            error_message = f"An error occurred during code generation: {e}"
            stack_trace = traceback.format_exc()
            logger.debug(error_message)
            logger.debug(f"Stack Trace:\n{stack_trace}")
            raise e

    def validate_and_clean_code(self, code: str) -> str:
        # Validate code requirements
        logger.debug("Validating code requirements...")
        code = self._code_validator.clean_code(code)
        if not self._code_validator.validate(code):
            raise ValueError("Code validation failed due to unmet requirements.")
        logger.debug("Code validation successful.")

        # Clean the code
        logger.debug("Cleaning the generated code...")
        return self._code_cleaner.clean_code(code)