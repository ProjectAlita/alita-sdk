from typing import Any, Optional, Dict
import asyncio
import json
from pydantic import create_model, Field

from alita_sdk.tools.elitea_base import BaseToolApiWrapper
from .deep_research import DeepResearcher
from .iterative_research import IterativeResearcher
from .llm_config import LLMConfig, create_default_config
from langchain_core.language_models.llms import BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel


class DeepResearcherWrapper(BaseToolApiWrapper):
    """Wrapper for deep_researcher module to be used as a LangChain toolkit."""
    alita: Any = None
    llm: Optional[BaseLLM | BaseChatModel] = None
    max_iterations: int = 5
    max_time_minutes: int = 10
    verbose: bool = False
    tracing: bool = False
    config: Optional[LLMConfig] = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize the config if not provided
        if not self.config:
            self.config = create_default_config(langchain_llm=self.llm)
        # Override llm in config if provided
        elif self.llm and not self.config.langchain_llm:
            # Create a new config with the langchain_llm
            self.config = create_default_config(langchain_llm=self.llm)
    
    def _setup_deep_researcher(self) -> DeepResearcher:
        """Initialize a DeepResearcher instance with current settings."""
        return DeepResearcher(
            max_iterations=self.max_iterations,
            max_time_minutes=self.max_time_minutes,
            verbose=self.verbose,
            tracing=self.tracing,
            config=self.config,
            llm=self.llm,
            alita=self.alita
        )
    
    def _setup_iterative_researcher(self) -> IterativeResearcher:
        """Initialize an IterativeResearcher instance with current settings."""
        return IterativeResearcher(
            max_iterations=self.max_iterations,
            max_time_minutes=self.max_time_minutes,
            verbose=self.verbose,
            tracing=self.tracing,
            config=self.config,
            llm=self.llm,
            alita=self.alita
        )
    
    def run_deep_research(self, query: str) -> str:
        """
        Run deep research on a query, breaking it down into sections and iteratively researching each part.
        
        Args:
            query: The research query
            
        Returns:
            Comprehensive research report
        """
        researcher = self._setup_deep_researcher()
        return asyncio.run(researcher.run(query))
    
    def run_iterative_research(self, query: str, output_length: str = "5 pages", output_instructions: str = "", background_context: str = "") -> str:
        """
        Run iterative research on a query, conducting multiple iterations to address knowledge gaps.
        
        Args:
            query: The research query
            output_length: Desired length of the output (e.g., "5 pages", "2 paragraphs")
            output_instructions: Additional instructions for output formatting
            background_context: Additional context to provide for the research
            
        Returns:
            Research report based on iterative findings
        """
        researcher = self._setup_iterative_researcher()
        return asyncio.run(researcher.run(
            query=query,
            output_length=output_length,
            output_instructions=output_instructions,
            background_context=background_context
        ))
    
    def get_available_tools(self):
        """Return the list of available tools."""
        return [
            {
                "name": "run_deep_research",
                "ref": self.run_deep_research,
                "description": self.run_deep_research.__doc__,
                "args_schema": create_model(
                    "DeepResearchModel",
                    query=(str, Field(description="The research query to investigate thoroughly"))
                )
            },
            {
                "name": "run_iterative_research",
                "ref": self.run_iterative_research,
                "description": self.run_iterative_research.__doc__,
                "args_schema": create_model(
                    "IterativeResearchModel",
                    query=(str, Field(description="The research query to investigate")),
                    output_length=(str, Field(description="Desired length of the output (e.g., '5 pages', '2 paragraphs')", default="5 pages")),
                    output_instructions=(str, Field(description="Additional instructions for output formatting", default="")),
                    background_context=(str, Field(description="Additional context to provide for the research", default=""))
                )
            }
        ]