# chat_message_template.py

**Path:** `src/alita_sdk/langchain/chat_message_template.py`

## Data Flow

The data flow within `chat_message_template.py` revolves around the transformation and formatting of chat messages using Jinja2 templates. The primary data elements are instances of `BaseMessage` and its subclasses (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). The data originates from the `message` parameter in the `_resolve_variables` method and is transformed by rendering Jinja2 templates with the provided keyword arguments (`kwargs`). The transformed data is then returned as a new instance of the appropriate message subclass. The `format_messages` method further processes these messages by iterating over a list of message templates, resolving variables, and appending the formatted messages to a result list.

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
In this example, the `_resolve_variables` method takes a `message` and `kwargs`, renders the message content using Jinja2, and returns a new message instance with the rendered content.

## Functions Descriptions

### `_resolve_variables`

This private method is responsible for resolving template variables within a message's content. It takes a `BaseMessage` instance and a dictionary of keyword arguments (`kwargs`). The method creates a Jinja2 environment, compiles the message content into a template, and renders it with the provided `kwargs`. Depending on the type of the original message, it returns a new instance of the appropriate subclass (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`) with the rendered content.

### `format_messages`

This method formats the chat template into a list of finalized messages. It takes keyword arguments (`kwargs`) to fill in template variables in all the template messages. The method merges partial and user-provided variables, iterates over the message templates, resolves variables for each template, and appends the formatted messages to a result list. It handles both `BaseMessage` instances and instances of `BaseMessagePromptTemplate` or `BaseChatPromptTemplate`.

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
In this example, the `format_messages` method processes each message template, resolves variables, and appends the formatted messages to the result list.

## Dependencies Used and Their Descriptions

### `logging`

Used for logging debug information, particularly the content of messages after they have been formatted.

### `typing`

Provides type hints for better code readability and maintainability.

### `jinja2`

Used for template rendering. The `Environment` and `DebugUndefined` classes are used to create a template environment and handle undefined variables during rendering.

### `langchain_core.prompts`

Imports `ChatPromptTemplate`, which is the base class for `Jinja2TemplatedChatMessagesTemplate`.

### `langchain_core.messages`

Imports various message classes (`BaseMessage`, `SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`) used to create and manipulate different types of chat messages.

### `langchain_core.prompts.chat`

Imports `BaseMessagePromptTemplate` and `BaseChatPromptTemplate`, which are used to handle more complex message templates within the `format_messages` method.

## Functional Flow

The functional flow of `chat_message_template.py` begins with the instantiation of the `Jinja2TemplatedChatMessagesTemplate` class. The primary methods `_resolve_variables` and `format_messages` are then used to process and format chat messages. The `_resolve_variables` method is called to render the content of individual messages using Jinja2 templates. The `format_messages` method iterates over a list of message templates, calls `_resolve_variables` for each template, and appends the formatted messages to a result list. The flow includes logging debug information for each formatted message.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. The primary focus is on processing and formatting chat messages using Jinja2 templates.