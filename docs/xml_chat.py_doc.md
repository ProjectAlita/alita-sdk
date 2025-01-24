# xml_chat.py

**Path:** `src/alita_sdk/langchain/agents/xml_chat.py`

## Data Flow

The data flow within `xml_chat.py` revolves around the creation and management of an XML-based chat agent. The primary data elements include intermediate steps, tools, prompts, and language model outputs. The data originates from user inputs and tool responses, which are formatted into XML messages. These messages are processed by the language model and the agent, which generates responses based on the provided tools and prompts.

For example, the `format_xml_messages` function takes intermediate steps as input and formats them into XML messages:

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
return thoughts
```

In this snippet, the intermediate steps are transformed into XML messages, which are then used by the agent to generate responses.

## Functions Descriptions

### `format_xml_messages`

This function formats intermediate steps into XML messages. It takes a list of tuples containing agent actions and observations as input and returns a list of formatted XML messages. The function iterates over the intermediate steps, creating XML logs for each action and observation, and appends them to a list of thoughts.

### `create_xml_chat_agent`

This function creates an XML-based chat agent. It takes a language model, tools, a prompt, and optional parameters for tools rendering and stop sequences. The function validates the prompt, binds the stop sequence to the language model, and creates a runnable sequence representing the agent. The agent processes inputs, generates XML messages, and returns either an AgentAction or AgentFinish.

## Dependencies Used and Their Descriptions

- `langchain_core._api`: Provides deprecated functionality.
- `langchain_core.language_models`: Contains the base language model class.
- `langchain_core.prompts.base`: Contains the base prompt template class.
- `langchain_core.runnables`: Provides runnable classes and passthrough functionality.
- `langchain_core.tools`: Contains the base tool class and tools renderer.
- `langchain.agents.output_parsers`: Provides the XML agent output parser.
- `langchain_core.agents`: Contains agent action classes.
- `langchain_core.messages`: Contains message classes for AI and human messages.

These dependencies are used to create and manage the XML-based chat agent, format messages, and handle tool interactions.

## Functional Flow

The functional flow of `xml_chat.py` involves the following steps:

1. **Formatting XML Messages:** The `format_xml_messages` function formats intermediate steps into XML messages.
2. **Creating the Agent:** The `create_xml_chat_agent` function creates an XML-based chat agent using the provided language model, tools, and prompt.
3. **Processing Inputs:** The agent processes user inputs and tool responses, generating XML messages and returning actions or final answers.

For example, the agent creation process involves validating the prompt, binding the stop sequence to the language model, and creating a runnable sequence:

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

## Endpoints Used/Created

The `xml_chat.py` file does not explicitly define or call any endpoints. The primary focus is on creating and managing an XML-based chat agent using the provided language model, tools, and prompt.