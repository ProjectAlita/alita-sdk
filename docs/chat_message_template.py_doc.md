# chat_message_template.py

**Path:** `src/alita_sdk/langchain/chat_message_template.py`

## Data Flow

The data flow within the `chat_message_template.py` file revolves around the transformation and formatting of chat messages using Jinja2 templates. The primary data elements are instances of `BaseMessage` and its subclasses (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). These messages are processed to replace template variables with actual values provided in the `kwargs` dictionary.

The `_resolve_variables` method is responsible for rendering the content of a message using Jinja2 templates. It takes a `BaseMessage` instance and a dictionary of keyword arguments (`kwargs`). The method creates a Jinja2 environment, compiles the message content as a template, and renders it with the provided `kwargs`. The rendered content is then used to create a new message instance of the same type as the original message.

The `format_messages` method orchestrates the overall data flow. It merges partial and user-provided variables into `kwargs`, iterates over the message templates, resolves variables for each message, and collects the formatted messages into a list.

Example:
```python
class Jinja2TemplatedChatMessagesTemplate(ChatPromptTemplate):
    def _resolve_variables(self, message: BaseMessage, kwargs: Dict) -> BaseMessage:
        environment = Environment(undefined=DebugUndefined)
        template = environment.from_string(message.content)
        content = template.render(kwargs)
        if isinstance(message, SystemMessage):
            return SystemMessage(content=content)
        elif isinstance(message, AIMessage):
            return AIMessage(content=content)
        elif isinstance(message, HumanMessage):
            return HumanMessage(content=content)
        elif isinstance(message, ToolMessage):
            return ToolMessage(content=content)
        else:
            return BaseMessage(content=content)
```

## Functions Descriptions

### `_resolve_variables`

This private method is designed to resolve template variables within a message's content. It takes two parameters: `message` (an instance of `BaseMessage`) and `kwargs` (a dictionary of keyword arguments). The method creates a Jinja2 environment with `DebugUndefined` to handle undefined variables. It then compiles the message content as a Jinja2 template and renders it using the provided `kwargs`. The rendered content is used to create a new message instance of the same type as the original message.

### `format_messages`

This method formats the chat template into a list of finalized messages. It takes keyword arguments (`kwargs`) to fill in template variables in all the template messages. The method merges partial and user-provided variables into `kwargs`, iterates over the message templates, resolves variables for each message, and collects the formatted messages into a list. It handles both `BaseMessage` instances and message prompt templates (`BaseMessagePromptTemplate`, `BaseChatPromptTemplate`).

Example:
```python
def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
    kwargs = self._merge_partial_and_user_variables(**kwargs)
    result = []
    for message_template in self.messages:
        if isinstance(message_template, BaseMessage):
            message = self._resolve_variables(message_template, kwargs)
            logger.debug(message.content)
            result.append(message)
        elif isinstance(message_template, 
                        (BaseMessagePromptTemplate, BaseChatPromptTemplate)
                        ):
            message = message_template.format_messages(**kwargs)
            result.extend(message)
    return result
```

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to create a logger for debugging purposes. It helps in tracking the flow of data and the state of the application by logging debug messages.

### `typing`

The `typing` module provides type hints for better code readability and maintainability. It is used to specify the types of parameters and return values in function signatures.

### `jinja2`

The `jinja2` library is used for template rendering. It allows the creation of templates with placeholders that can be dynamically replaced with actual values. In this file, it is used to render the content of chat messages with the provided `kwargs`.

### `langchain_core.prompts`

The `langchain_core.prompts` module provides the `ChatPromptTemplate` class, which is the base class for `Jinja2TemplatedChatMessagesTemplate`. It defines the structure and behavior of chat prompt templates.

### `langchain_core.messages`

The `langchain_core.messages` module provides various message classes (`BaseMessage`, `SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). These classes represent different types of messages that can be used in chat templates.

## Functional Flow

The functional flow of the `chat_message_template.py` file involves the following steps:

1. **Initialization**: The `Jinja2TemplatedChatMessagesTemplate` class is defined, inheriting from `ChatPromptTemplate`.
2. **Variable Resolution**: The `_resolve_variables` method is used to render the content of a message with the provided `kwargs`.
3. **Message Formatting**: The `format_messages` method orchestrates the overall process of formatting chat messages. It merges variables, iterates over message templates, resolves variables, and collects formatted messages into a list.
4. **Logging**: Debug messages are logged to track the content of formatted messages.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on the internal processing and formatting of chat messages using Jinja2 templates.