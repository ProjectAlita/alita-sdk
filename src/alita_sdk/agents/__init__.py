from __future__ import annotations
import logging
from typing import Optional, Sequence

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import BasePromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.tools import BaseTool

from langchain.agents import AgentOutputParser
from langchain.agents.format_scratchpad import format_log_to_str

from langchain.tools.render import ToolsRenderer

from .mixedAgentRenderes import render_text_description_and_args, format_log_to_str
from .mixedAgentParser import MixedAgentOutputParser, FORMAT_INSTRUCTIONS

logger = logging.getLogger(__name__)


def create_mixed_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    output_parser: Optional[AgentOutputParser] = None,
    tools_renderer: ToolsRenderer = render_text_description_and_args,
) -> Runnable:
    """Create mixed agent that uses ReAct prompting.

    Args:
        llm: LLM to use as the agent.
        tools: Tools this agent has access to.
        prompt: The prompt to use. See Prompt section below for more.
        output_parser: AgentOutputParser for parse the LLM output.
        tools_renderer: This controls how the tools are converted into a string and
            then passed into the LLM. Default is `render_text_description`.

    Returns:
        A Runnable sequence representing an agent. It takes as input all the same input
        variables as the prompt passed in does. It returns as output either an
        AgentAction or AgentFinish.
    """  # noqa: E501
    missing_vars = {"tools", "tool_names", "agent_scratchpad"}.difference(
        prompt.input_variables
    )
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")

    prompt = prompt.partial(
        tools=tools_renderer(list(tools)),
        tool_names=", ".join([t.name for t in tools]),
        response_format = FORMAT_INSTRUCTIONS
    )
    # llm_with_stop = llm.bind(stop=["\"tool\":", "Running Tool:"])
    output_parser = output_parser or MixedAgentOutputParser()
    logger.debug("Prompt in mixed agent: %s", prompt)
    agent = (
        RunnablePassthrough.assign(
            agent_scratchpad=lambda x: format_log_to_str(x['intermediate_steps']),
        )
        | prompt
        | llm
        | output_parser
    )
    return agent
