"""
Agent used to perform web searches and summarize the results.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple query string as input

The Agent then:
1. Uses the web_search tool to retrieve search results
2. Analyzes the retrieved information
3. Writes a 3+ paragraph summary of the search results
4. Includes citations/URLs in brackets next to information sources
5. Returns the formatted summary as a string

The agent can use either OpenAI's built-in web search capability or a custom
web search implementation based on environment configuration.
"""

from langchain_core.tools import Tool
from typing import Dict, Any, List

from . import ToolAgentOutput
from ...llm_config import LLMConfig
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are a research assistant that specializes in retrieving and summarizing information from the web.

OBJECTIVE:
Given an AgentTask, follow these steps:
- Convert the 'query' into an optimized SERP search term for Google, limited to 3-5 words
- If an 'entity_website' is provided, make sure to include the domain name in your optimized Google search term
- Enter the optimized search term into the web_search tool
- After using the web_search tool, write a 3+ paragraph summary that captures the main points from the search results

GUIDELINES:
- In your summary, try to comprehensively answer/address the 'gap' provided (which is the objective of the search)
- The summary should always quote detailed facts, figures and numbers where these are available
- If the search results are not relevant to the search term or do not address the 'gap', simply write "No relevant results found"
- Use headings and bullets to organize the summary if needed
- Include citations/URLs in brackets next to all associated information in your summary
- Do not make additional searches

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""

def init_search_agent(config: LLMConfig) -> ResearchAgent:
    """
    Initialize a search agent using LangChain tools.
    
    Args:
        config: The LLM configuration to use
        
    Returns:
        A ResearchAgent that can search the web and summarize results
    """
    # Create a LangChain wrapper around the web_search tool
    async def web_search_wrapper(query: str, num_results: int = 8) -> List[Dict[str, Any]]:
        """
        Perform a web search and return the results.
        
        Args:
            query: The query to search for
            num_results: Number of results to return
            
        Returns:
            A list of search results with title, url, and snippet
        """
        # Import here to avoid circular imports
        from ...tools import web_search
        
        # Use the original web_search function
        results = await web_search(query, num_results)
        return results
    
    # Create a LangChain Tool
    web_search_tool = Tool(
        name="web_search",
        description="Search the web for information on a specific query. Returns a list of search results.",
        func=web_search_wrapper,
        coroutine=web_search_wrapper,
    )
    
    # Use our adapter to initialize the agent with the LangChain tool
    selected_model = config.fast_model
    
    # Determine whether to use structured output
    use_output_parser = not hasattr(selected_model, 'langchain_llm')
    
    return ResearchAgent(
        name="WebSearchAgent",
        instructions=INSTRUCTIONS,
        tools=[web_search_tool],
        model=selected_model.langchain_llm if hasattr(selected_model, 'langchain_llm') else selected_model,
        output_type=ToolAgentOutput if not use_output_parser else None,
        output_parser=create_type_parser(ToolAgentOutput) if use_output_parser else None
    )