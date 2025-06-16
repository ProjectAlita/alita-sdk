from langchain_core.tools import BaseTool
from typing import Type
from pydantic import create_model, BaseModel, Field
from langchain_community.utilities.google_search import GoogleSearchAPIWrapper
from .utils import webRag


class GoogleSearchResults(BaseTool):
    """Tool that queries the Google Search API and gets back json."""
    api_wrapper: GoogleSearchAPIWrapper = None
    name: str = "google_search_results_json"
    description: str = (
        "A wrapper around Google Search. "
        "Useful for when you need to answer questions about current events. "
        "Input should be a search query. Output is a JSON array of the query results"
    )
    num_results: int = 4
    args_schema: Type[BaseModel] = create_model(
        "GoogleSearchResultsModel",
        query=(str, Field(description="Query text to search pages")))

    def _run(self, query: str, run_manager = None,) -> str:
        """Use the tool."""
        return str(self.api_wrapper.results(query, self.num_results))


class GoogleSearchRag(BaseTool):
    googleApiWrapper: GoogleSearchAPIWrapper = None
    max_response_size: int = 3000
    name: str = "google_search_with_scrapper"
    description: str = "Searches Google for 5 top results, reads the pages and searches for relevant content"
    num_results: int = 5
    args_schema: Type[BaseModel] = create_model(
        "GoogleSearchRagModel",
        query=(str, Field(description="Query text to search pages")))

    def _run(self, query: str, run_manager=None) -> str:
        results = self.googleApiWrapper.results(query, self.num_results)
        urls = []
        snippets = ""
        for result in results:
            urls.append(result['link'])
            snippets += f"\n\n{result['title']}\n{result['snippet']}"
        return snippets + webRag(urls, self.max_response_size, query)


