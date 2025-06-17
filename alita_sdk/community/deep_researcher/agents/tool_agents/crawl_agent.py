"""
Agent used to crawl a website and return the results.

The CrawlAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple starting url string as input

The Agent then:
1. Uses the crawl_website tool to crawl the website
2. Writes a 3+ paragraph summary of the crawled contents
3. Includes citations/URLs in brackets next to information sources
4. Returns the formatted summary as a string
"""

from langchain_core.tools import Tool
from typing import Dict, Any

from . import ToolAgentOutput
from ...llm_config import LLMConfig
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""
You are a web crawling agent that crawls the contents of a website and answers a query based on the crawled contents. Follow these steps exactly:

* From the provided information, use the 'entity_website' as the starting_url for the web crawler
* Crawl the website using the crawl_website tool
* After using the crawl_website tool, write a 3+ paragraph summary that captures the main points from the crawled contents
* In your summary, try to comprehensively answer/address the 'gaps' and 'query' provided (if available)
* If the crawled contents are not relevant to the 'gaps' or 'query', simply write "No relevant results found"
* Use headings and bullets to organize the summary if needed
* Include citations/URLs in brackets next to all associated information in your summary
* Only run the crawler once

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""

def init_crawl_agent(config: LLMConfig) -> ResearchAgent:
    """
    Initialize a crawl agent using LangChain tools.
    
    Args:
        config: The LLM configuration to use
        
    Returns:
        A ResearchAgent that can crawl websites
    """
    # Create a LangChain wrapper around the crawl_website tool
    async def crawl_website_wrapper(starting_url: str, max_links: int = 5) -> str:
        """
        Crawl a website and extract its main content.
        
        Args:
            starting_url: The URL to start crawling from
            max_links: Maximum number of links to follow from the starting page
            
        Returns:
            The extracted content from the website
        """
        from ...tools import crawl_website
        # Import inside function to avoid circular imports
        
        # Use the original crawl_website function
        result = await crawl_website(starting_url, max_links)
        return result
    
    # Create a LangChain Tool
    crawl_tool = Tool(
        name="crawl_website",
        description="Crawls a website and extracts its main content starting from the provided URL",
        func=crawl_website_wrapper,
        coroutine=crawl_website_wrapper,
    )
    
    # Use our adapter to initialize the agent with the LangChain tool
    selected_model = config.fast_model
    
    # Determine whether to use structured output
    use_output_parser = not hasattr(selected_model, 'langchain_llm')
    
    return ResearchAgent(
        name="SiteCrawlerAgent",
        instructions=INSTRUCTIONS,
        tools=[crawl_tool],
        model=selected_model.langchain_llm if hasattr(selected_model, 'langchain_llm') else selected_model,
        output_type=ToolAgentOutput if not use_output_parser else None,
        output_parser=create_type_parser(ToolAgentOutput) if use_output_parser else None
    )
