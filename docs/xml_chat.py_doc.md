# xml_chat.py

**Path:** `src/alita_sdk/langchain/agents/xml_chat.py`

## Data Flow

The data flow within `xml_chat.py` revolves around the creation and utilization of an XML-based chat agent. The primary data elements include intermediate steps, tools, prompts, and language model outputs. The data originates from user inputs and tool responses, which are formatted as XML messages. These messages are processed by the language model and the agent, resulting in either an agent action or a final answer. The data is manipulated through various transformations, such as formatting intermediate steps into XML and rendering tool descriptions. The direction of data movement is from user input to tool invocation, followed by language model processing and agent response generation. Intermediate variables like `thoughts` and `log` are used to temporarily store formatted messages and observations.

Example:
```python
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
```
This snippet illustrates the transformation of intermediate steps into XML messages, which are then used to generate agent responses.

## Functions Descriptions

### `format_xml_messages`

This function formats intermediate steps as XML messages. It takes a list of tuples containing agent actions and observations as input and returns a list of formatted XML messages. The function iterates over the intermediate steps, creating XML logs for each action and observation, and appends them to the `thoughts` list. The final list of XML messages is returned.

### `create_xml_chat_agent`

This function creates an XML-based chat agent using a language model, tools, and a prompt. It takes several parameters, including the language model (`llm`), tools, prompt, tools renderer, and stop sequence. The function validates the prompt, sets up the tools renderer, and configures the language model with stop sequences if necessary. It then constructs a runnable sequence representing the agent, which processes input variables and returns either an agent action or a final answer.

Example:
```python
agent = (
    RunnablePassthrough.assign(
        agent_scratchpad=lambda x: format_xml_messages(x["intermediate_steps"])
    )
    | prompt
    | llm_with_stop
    | XMLAgentOutputParser()
)
return agent
```
This snippet shows the construction of the agent using a sequence of runnables, including the formatting of intermediate steps, prompt processing, language model invocation, and output parsing.

## Dependencies Used and Their Descriptions

- `langchain_core._api`: Provides deprecated API functionalities.
- `langchain_core.language_models.BaseLanguageModel`: Represents the base class for language models used by the agent.
- `langchain_core.prompts.base.BasePromptTemplate`: Represents the base class for prompt templates used by the agent.
- `langchain_core.runnables.Runnable`, `RunnablePassthrough`: Provides runnable components for constructing the agent's processing sequence.
- `langchain_core.tools.BaseTool`: Represents the base class for tools used by the agent.
- `langchain_core.tools.render.ToolsRenderer`, `render_text_description`: Provides rendering functionalities for tool descriptions.
- `langchain.agents.output_parsers.XMLAgentOutputParser`: Parses the agent's output formatted as XML.
- `langchain_core.agents.AgentAction`: Represents actions taken by the agent.
- `langchain_core.messages.AIMessage`, `BaseMessage`, `HumanMessage`: Represents different types of messages used in the agent's communication.

These dependencies provide the necessary components for creating and managing the XML-based chat agent, including language models, prompts, tools, runnables, and message handling.

## Functional Flow

The functional flow of `xml_chat.py` involves the following steps:
1. **Formatting Intermediate Steps**: The `format_xml_messages` function formats intermediate steps as XML messages.
2. **Creating the Agent**: The `create_xml_chat_agent` function creates an XML-based chat agent using the provided language model, tools, and prompt.
3. **Validating the Prompt**: The function checks if the prompt contains the required input variables and raises an error if any are missing.
4. **Setting Up Tools Renderer**: The function sets up the tools renderer to convert tool descriptions into a string format.
5. **Configuring Language Model**: The function configures the language model with stop sequences if necessary.
6. **Constructing the Agent**: The function constructs a runnable sequence representing the agent, which processes input variables and returns either an agent action or a final answer.

Example:
```python
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
```
This snippet demonstrates the validation of the prompt, setup of the tools renderer, configuration of the language model, and construction of the agent.

## Endpoints Used/Created

The `xml_chat.py` file does not explicitly define or call any endpoints. The functionality is focused on creating an XML-based chat agent using language models, tools, and prompts. The agent processes user inputs and tool responses, generating XML-formatted messages and actions. The interaction with external systems or endpoints is abstracted through the tools and language model used by the agent.