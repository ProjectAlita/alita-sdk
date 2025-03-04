# xml_chat.py

**Path:** `src/alita_sdk/langchain/agents/xml_chat.py`

## Data Flow

The data flow within `xml_chat.py` revolves around the creation and utilization of an XML-based chat agent. The primary data elements include intermediate steps, language model inputs, and tool descriptions. The data originates from user inputs and tool outputs, which are formatted into XML structures. These XML structures are then processed by the language model to generate responses. The data flow can be summarized as follows:

1. **User Input:** The user provides input, which is processed by the language model.
2. **Intermediate Steps:** These steps are formatted into XML using the `format_xml_messages` function.
3. **Tool Descriptions:** Tools available to the agent are described and rendered into text.
4. **Language Model Processing:** The language model processes the XML-formatted data and tool descriptions to generate responses.
5. **Output:** The final output is either an agent action or a final answer in XML format.

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
This snippet shows how intermediate steps are formatted into XML and appended to the thoughts list.

## Functions Descriptions

### `format_xml_messages`

This function formats intermediate steps into XML. It takes a list of tuples containing agent actions and observations and returns a list of `BaseMessage` objects formatted as XML.

- **Parameters:**
  - `intermediate_steps` (List[Tuple[AgentAction, str]]): The intermediate steps to be formatted.
- **Returns:**
  - `List[BaseMessage]`: The formatted intermediate steps as XML messages.

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
This example demonstrates how the function processes intermediate steps and formats them into XML.

### `create_xml_chat_agent`

This function creates an XML-based chat agent using a language model, tools, and a prompt. It returns a `Runnable` sequence representing the agent.

- **Parameters:**
  - `llm` (BaseLanguageModel): The language model to use as the agent.
  - `tools` (Sequence[BaseTool]): The tools available to the agent.
  - `prompt` (BasePromptTemplate): The prompt template to use.
  - `tools_renderer` (ToolsRenderer): Optional. Controls how tools are rendered into text. Default is `render_text_description`.
  - `stop_sequence` (Union[bool, List[str]]): Optional. Controls the stop sequence for the language model. Default is `True`.
- **Returns:**
  - `Runnable`: A sequence representing the agent.

Example:
```python
prompt = hub.pull("hwchase17/xml-agent-convo")
model = ChatAnthropic(model="claude-3-haiku-20240307")
tools = ...

agent = create_xml_agent(model, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

agent_executor.invoke({"input": "hi"})
```
This example shows how to create and use an XML-based chat agent.

## Dependencies Used and Their Descriptions

- `langchain_core._api`: Provides deprecated API functionalities.
- `langchain_core.language_models`: Contains the `BaseLanguageModel` class used for language model operations.
- `langchain_core.prompts.base`: Contains the `BasePromptTemplate` class used for prompt templates.
- `langchain_core.runnables`: Provides the `Runnable` and `RunnablePassthrough` classes for creating runnable sequences.
- `langchain_core.tools`: Contains the `BaseTool` class and `ToolsRenderer` for tool operations and rendering.
- `langchain.agents.output_parsers`: Provides the `XMLAgentOutputParser` for parsing agent outputs in XML format.
- `langchain_core.agents`: Contains the `AgentAction` class for agent actions.
- `langchain_core.messages`: Provides the `AIMessage`, `BaseMessage`, and `HumanMessage` classes for message handling.

These dependencies are essential for creating and managing the XML-based chat agent, handling language model operations, and formatting messages and tool descriptions.

## Functional Flow

The functional flow of `xml_chat.py` involves the following steps:

1. **Formatting Intermediate Steps:** The `format_xml_messages` function formats intermediate steps into XML messages.
2. **Creating the Agent:** The `create_xml_chat_agent` function creates an XML-based chat agent using the provided language model, tools, and prompt.
3. **Rendering Tools:** The tools are rendered into text descriptions using the `tools_renderer`.
4. **Processing User Input:** The agent processes user input and generates responses based on the XML-formatted intermediate steps and tool descriptions.
5. **Generating Output:** The final output is either an agent action or a final answer in XML format.

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
This example shows the creation of the agent by combining various components into a runnable sequence.

## Endpoints Used/Created

The `xml_chat.py` file does not explicitly define or call any endpoints. The primary focus is on creating an XML-based chat agent using a language model and tools. The interactions are handled within the code through function calls and data processing, without involving external endpoints.