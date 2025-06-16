"""Tool for the Wikipedia API."""
from typing import Optional, Type

from pydantic import create_model, BaseModel, Field
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool

from langchain_community.utilities.wikipedia import WikipediaAPIWrapper


class WikipediaQueryRun(BaseTool):
    """Tool that searches the Wikipedia API."""

    name: str = "wikipedia"
    description: str = (
        "A wrapper around Wikipedia. "
        "Useful for when you need to answer general questions about "
        "people, places, companies, facts, historical events, or other subjects. "
        "Input should be a search query."
    )
    api_wrapper: WikipediaAPIWrapper = None  # Add default None value
    args_schema: Type[BaseModel] = create_model("WikipediaQueryRunModel",
                                 query=(str, Field(description="Query text to search pages")))

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the Wikipedia tool."""
        return self.api_wrapper.run(query)
