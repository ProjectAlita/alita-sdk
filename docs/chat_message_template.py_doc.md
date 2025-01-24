# chat_message_template.py

**Path:** `src/alita_sdk/langchain/chat_message_template.py`

## Data Flow

The data flow within `chat_message_template.py` revolves around the transformation and formatting of chat messages using Jinja2 templates. The primary data elements are instances of `BaseMessage` and its subclasses (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). The data originates from the `message` parameter in the `_resolve_variables` method and is transformed by rendering Jinja2 templates with the provided `kwargs`. The transformed data is then returned as a new instance of the appropriate message subclass. The `format_messages` method further processes these messages by iterating over a list of message templates, resolving variables, and appending the formatted messages to a result list.

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

This private method is responsible for rendering the content of a `BaseMessage` instance using Jinja2 templates. It takes a `message` and a dictionary of keyword arguments (`kwargs`). The method creates a Jinja2 environment, compiles the message content into a template, and renders it with the provided `kwargs`. Depending on the type of the original message, it returns a new instance of the appropriate subclass (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`) with the rendered content.

### `format_messages`

This method formats the chat template into a list of finalized messages. It takes keyword arguments (`kwargs`) to fill in template variables in all the template messages. The method merges partial and user variables, iterates over the message templates, resolves variables for each message, and appends the formatted messages to a result list. If a message template is an instance of `BaseMessagePromptTemplate` or `BaseChatPromptTemplate`, it calls their `format_messages` method and extends the result list with the returned messages.

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

The `logging` module is used to create a logger for debugging purposes. It logs the content of messages during the formatting process.

### `typing`

The `typing` module provides type hints for better code readability and maintainability. It is used to specify the types of parameters and return values in the methods.

### `jinja2`

The `jinja2` module is used for rendering templates. It provides the `Environment` and `DebugUndefined` classes to create a template environment and handle undefined variables during rendering.

### `langchain_core.prompts`

The `langchain_core.prompts` module provides the `ChatPromptTemplate` class, which is the base class for `Jinja2TemplatedChatMessagesTemplate`.

### `langchain_core.messages`

The `langchain_core.messages` module provides various message classes (`BaseMessage`, `SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`) used to represent different types of chat messages.

### `langchain_core.prompts.chat`

The `langchain_core.prompts.chat` module provides the `BaseMessagePromptTemplate` and `BaseChatPromptTemplate` classes, which are used to format messages in the chat template.

## Functional Flow

The functional flow of `chat_message_template.py` involves the following steps:
1. The `format_messages` method is called with keyword arguments (`kwargs`).
2. The method merges partial and user variables using `_merge_partial_and_user_variables`.
3. It initializes an empty result list.
4. The method iterates over the message templates in `self.messages`.
5. For each message template, it checks if it is an instance of `BaseMessage`.
6. If it is, the method calls `_resolve_variables` to render the message content and appends the formatted message to the result list.
7. If the message template is an instance of `BaseMessagePromptTemplate` or `BaseChatPromptTemplate`, it calls their `format_messages` method and extends the result list with the returned messages.
8. The method returns the result list of formatted messages.

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

## Endpoints Used/Created

There are no explicit endpoints used or created in `chat_message_template.py`. The file focuses on formatting chat messages using Jinja2 templates and does not interact with external services or APIs.