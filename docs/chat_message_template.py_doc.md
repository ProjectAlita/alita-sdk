# chat_message_template.py

**Path:** `src/alita_sdk/langchain/chat_message_template.py`

## Data Flow

The data flow within the `chat_message_template.py` file revolves around the creation and formatting of chat messages using Jinja2 templates. The primary data elements are instances of `BaseMessage` and its subclasses (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). The data originates from the input arguments provided to the `format_messages` method, which are keyword arguments (`kwargs`) used to fill in template variables. These variables are merged with partial and user variables to form a complete set of data for rendering the templates.

The `_resolve_variables` method is responsible for transforming the content of each message by rendering the Jinja2 template with the provided data. The transformed content is then used to create a new message instance of the appropriate type. The formatted messages are collected in a list and returned by the `format_messages` method.

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
In this example, the `_resolve_variables` method takes a `BaseMessage` instance and a dictionary of keyword arguments, renders the message content using Jinja2, and returns a new message instance with the rendered content.

## Functions Descriptions

### `_resolve_variables`

The `_resolve_variables` method is a private method that resolves the variables in a message's content using Jinja2 templates. It takes a `BaseMessage` instance and a dictionary of keyword arguments (`kwargs`). The method creates a Jinja2 environment with `DebugUndefined` to handle undefined variables. It then renders the message content using the provided `kwargs` and returns a new message instance of the appropriate type (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`, or `BaseMessage`).

### `format_messages`

The `format_messages` method formats the chat template into a list of finalized messages. It takes keyword arguments (`kwargs`) to fill in template variables in all the template messages. The method merges partial and user variables with the provided `kwargs` and iterates over the message templates. For each message template, it resolves the variables using `_resolve_variables` if the template is a `BaseMessage` instance, or calls `format_messages` recursively if the template is an instance of `BaseMessagePromptTemplate` or `BaseChatPromptTemplate`. The formatted messages are collected in a list and returned.

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
In this example, the `format_messages` method formats the chat template by resolving variables in each message template and collecting the formatted messages in a list.

## Dependencies Used and Their Descriptions

### `logging`

The `logging` module is used to create a logger for debugging purposes. The logger is configured to log messages with the name of the current module (`__name__`).

### `typing`

The `typing` module is used for type hinting. It provides type hints for the method arguments and return types, such as `Any`, `Dict`, and `List`.

### `jinja2`

The `jinja2` module is used for template rendering. The `Environment` class is used to create a Jinja2 environment, and `DebugUndefined` is used to handle undefined variables in the templates. The `from_string` method is used to create a template from a string, and the `render` method is used to render the template with the provided data.

### `langchain_core.prompts`

The `langchain_core.prompts` module provides the `ChatPromptTemplate` class, which is the base class for `Jinja2TemplatedChatMessagesTemplate`.

### `langchain_core.messages`

The `langchain_core.messages` module provides the `BaseMessage` class and its subclasses (`SystemMessage`, `AIMessage`, `HumanMessage`, `ToolMessage`). These classes represent different types of chat messages.

### `langchain_core.prompts.chat`

The `langchain_core.prompts.chat` module provides the `BaseMessagePromptTemplate` and `BaseChatPromptTemplate` classes, which are used for formatting chat messages.

## Functional Flow

The functional flow of the `chat_message_template.py` file involves the following steps:

1. The `format_messages` method is called with keyword arguments (`kwargs`) to fill in template variables.
2. The method merges partial and user variables with the provided `kwargs`.
3. The method iterates over the message templates in the `messages` attribute.
4. For each message template, the method resolves the variables using `_resolve_variables` if the template is a `BaseMessage` instance, or calls `format_messages` recursively if the template is an instance of `BaseMessagePromptTemplate` or `BaseChatPromptTemplate`.
5. The formatted messages are collected in a list and returned.

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
In this example, the `format_messages` method formats the chat template by resolving variables in each message template and collecting the formatted messages in a list.

## Endpoints Used/Created

The `chat_message_template.py` file does not explicitly define or call any endpoints. The primary functionality of the file is to format chat messages using Jinja2 templates and the provided data.