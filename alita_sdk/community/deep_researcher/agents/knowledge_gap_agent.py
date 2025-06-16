"""
Agent used to evaluate the state of the research report (typically done in a loop) and identify knowledge gaps that still 
need to be addressed.

The Agent takes as input a string in the following format:
===========================================================
ORIGINAL QUERY: <original user query>

HISTORY OF ACTIONS, FINDINGS AND THOUGHTS: <breakdown of activities and findings carried out so far>
===========================================================

The Agent then:
1. Carefully reviews the current draft and assesses its completeness in answering the original query
2. Identifies specific knowledge gaps that still exist and need to be filled
3. Returns a KnowledgeGapOutput object
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from langchain_core.tools import BaseTool
from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from datetime import datetime
from .utils.parse_output import create_type_parser

class KnowledgeGapOutput(BaseModel):
    """Output from the Knowledge Gap Agent"""
    research_complete: bool = Field(description="Whether the research and findings are complete enough to end the research loop")
    outstanding_gaps: List[str] = Field(description="List of knowledge gaps that still need to be addressed")


INSTRUCTIONS = f"""
You are a Research State Evaluator. Today's date is {datetime.now().strftime("%Y-%m-%d")}.
Your job is to critically analyze the current state of a research report, 
identify what knowledge gaps still exist and determine the best next step to take.

You will be given:
1. The original user query and any relevant background context to the query
2. A full history of the tasks, actions, findings and thoughts you've made up until this point in the research process

Your task is to:
1. Carefully review the findings and thoughts, particularly from the latest iteration, and assess their completeness in answering the original query
2. Determine if the findings are sufficiently complete to end the research loop
3. If not, identify up to 3 knowledge gaps that need to be addressed in sequence in order to continue with research - these should be relevant to the original query

Be specific in the gaps you identify and include relevant information as this will be passed onto another agent to process without additional context.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{KnowledgeGapOutput.model_json_schema()}
"""

def init_knowledge_gap_agent(config: LLMConfig) -> ResearchAgent:
    """
    Initialize the knowledge gap agent.
    
    Args:
        config: The LLM configuration to use
        
    Returns:
        A ResearchAgent that can evaluate knowledge gaps
    """
    selected_model = config.fast_model
    
    # Determine whether to use structured output based on if we have a Langchain LLM
    use_output_parser = not hasattr(selected_model, 'langchain_llm')
    
    return ResearchAgent(
        name="KnowledgeGapAgent",
        instructions=INSTRUCTIONS,
        tools=[],  # No tools needed for this agent
        model=selected_model.langchain_llm if hasattr(selected_model, 'langchain_llm') else selected_model,
        output_type=KnowledgeGapOutput if not use_output_parser else None,
        output_parser=create_type_parser(KnowledgeGapOutput) if use_output_parser else None
    )