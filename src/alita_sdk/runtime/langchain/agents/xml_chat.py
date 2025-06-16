from typing import Any, List, Sequence, Union, List, Tuple

from langchain_core._api import deprecated
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.tools.render import ToolsRenderer, render_text_description
from langchain.agents.output_parsers import XMLAgentOutputParser


from langchain_core.agents import AgentAction
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

def format_xml_messages(
    intermediate_steps: List[Tuple[AgentAction, str]],
) -> str:
    """Format the intermediate steps as XML.

    Args:
        intermediate_steps: The intermediate steps.

    Returns:
        The intermediate steps as XML.
    """
    thoughts: List[BaseMessage] = []
    for action, observation in intermediate_steps:
        log = (
            f"<tool>{action.tool}</tool><tool_input>{action.tool_input}</tool_input>"
        )
        thoughts.append(AIMessage(content=log))
        human_message = HumanMessage(f"""
TOOL RESPONSE: 
---------------------
{observation}

USER'S INPUT
--------------------
Okay, so what is the response to my last comment? 
If using information obtained from the tools you must mention it explicitly without mentioning the tool names 
- I have forgotten all TOOL RESPONSES! 
Remember to respond with a XML blob with a single action or final_answer with nice markdown; and NOTHING else - even if you just want to respond to the user. Do NOT respond with anything except a XML snippet no matter what!""")
        thoughts.append(human_message)
    return thoughts



def create_xml_chat_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    tools_renderer: ToolsRenderer = render_text_description,
    *,
    stop_sequence: Union[bool, List[str]] = True,
) -> Runnable:
    """Create an agent that uses XML to format its logic.

    Args:
        llm: LLM to use as the agent.
        tools: Tools this agent has access to.
        prompt: The prompt to use, must have input keys
            `tools`: contains descriptions for each tool.
            `agent_scratchpad`: contains previous agent actions and tool outputs.
        tools_renderer: This controls how the tools are converted into a string and
            then passed into the LLM. Default is `render_text_description`.
        stop_sequence: bool or list of str.
            If True, adds a stop token of "</tool_input>" to avoid hallucinates.
            If False, does not add a stop token.
            If a list of str, uses the provided list as the stop tokens.

            Default is True. You may to set this to False if the LLM you are using
            does not support stop sequences.

    Returns:
        A Runnable sequence representing an agent. It takes as input all the same input
        variables as the prompt passed in does. It returns as output either an
        AgentAction or AgentFinish.

    Example:

        .. code-block:: python

            from langchain import hub
            from langchain_community.chat_models import ChatAnthropic
            from langchain.agents import AgentExecutor, create_xml_agent

            prompt = hub.pull("hwchase17/xml-agent-convo")
            model = ChatAnthropic(model="claude-3-haiku-20240307")
            tools = ...

            agent = create_xml_agent(model, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools)

            agent_executor.invoke({"input": "hi"})

            # Use with chat history
            from langchain_core.messages import AIMessage, HumanMessage
            agent_executor.invoke(
                {
                    "input": "what's my name?",
                    # Notice that chat_history is a string
                    # since this prompt is aimed at LLMs, not chat models
                    "chat_history": "Human: My name is Bob\\nAI: Hello Bob!",
                }
            )

    Prompt:

        The prompt must have input keys:
            * `tools`: contains descriptions for each tool.
            * `agent_scratchpad`: contains previous agent actions and tool outputs as an XML string.

        Here's an example:

        .. code-block:: python

            from langchain_core.prompts import PromptTemplate

            template = '''You are a helpful assistant. Help the user answer any questions.

            You have access to the following tools:

            {tools}

            In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>
            For example, if you have a tool called 'search' that could run a google search, in order to search for the weather in SF you would respond:

            <tool>search</tool><tool_input>weather in SF</tool_input>
            <observation>64 degrees</observation>

            When you are done, respond with a final answer between <final_answer></final_answer>. For example:

            <final_answer>The weather in SF is 64 degrees</final_answer>

            Begin!

            Previous Conversation:
            {chat_history}

            Question: {input}
            {agent_scratchpad}'''
            prompt = PromptTemplate.from_template(template)
    """  # noqa: E501
    missing_vars = {"tools", "tool_names", "agent_scratchpad"}.difference(
        prompt.input_variables + list(prompt.partial_variables)
    )
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")
    
    prompt = prompt.partial(
        tools=tools_renderer(list(tools)),
    )

    if stop_sequence:
        stop = ["\nObservation"] if stop_sequence is True else stop_sequence
        llm_with_stop = llm.bind(stop=stop)
    else:
        llm_with_stop = llm

    agent = (
        RunnablePassthrough.assign(
            agent_scratchpad=lambda x: format_xml_messages(x["intermediate_steps"])
        )
        | prompt
        | llm_with_stop
        | XMLAgentOutputParser()
    )
    return agent
