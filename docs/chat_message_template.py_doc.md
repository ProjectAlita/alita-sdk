# chat_message_template.py

**Path:** `src/alita_sdk/langchain/chat_message_template.py`

## Data Flow

The data flow within the `chat_message_template.py` file revolves around the creation and formatting of chat messages using Jinja2 templates. The primary class, `Jinja2TemplatedChatMessagesTemplate`, extends `ChatPromptTemplate` and is responsible for resolving variables within message templates and formatting them into finalized messages. The data flow can be summarized as follows:

1. **Input Data:** The input data consists of message templates and keyword arguments (`kwargs`) that provide values for the template variables.
2. **Template Resolution:** The `_resolve_variables` method uses the Jinja2 `Environment` to create a template from the message content and renders it with the provided `kwargs`. This results in a new message with the resolved content.
3. **Message Formatting:** The `format_messages` method iterates over the message templates, resolves the variables for each template, and collects the formatted messages into a list.
4. **Output Data:** The output is a list of formatted messages with the template variables replaced by the corresponding values from `kwargs`.

### Example:
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
*In this example, the `_resolve_variables` method takes a message and `kwargs`, creates a Jinja2 template from the message content, and renders it with `kwargs` to produce a new message with the resolved content.*

## Functions Descriptions

### `Jinja2TemplatedChatMessagesTemplate`

#### `_resolve_variables`

- **Purpose:** Resolves template variables within a message using Jinja2.
- **Inputs:**
  - `message` (BaseMessage): The message containing the template content.
  - `kwargs` (Dict): A dictionary of keyword arguments to use for resolving the template variables.
- **Processing Logic:**
  - Creates a Jinja2 `Environment` with `DebugUndefined` to handle undefined variables.
  - Converts the message content into a Jinja2 template.
  - Renders the template with the provided `kwargs` to produce the resolved content.
  - Returns a new message of the same type as the input message with the resolved content.
- **Outputs:** A new message with the resolved content.

#### `format_messages`

- **Purpose:** Formats the chat template into a list of finalized messages.
- **Inputs:**
  - `kwargs` (Any): Keyword arguments to use for filling in template variables in all the template messages.
- **Processing Logic:**
  - Merges partial and user-provided variables using `_merge_partial_and_user_variables`.
  - Iterates over the message templates in `self.messages`.
  - Resolves variables for each message template and collects the formatted messages into a list.
- **Outputs:** A list of formatted messages.

### Example:
```python
def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
    """Format the chat template into a list of finalized messages.

    Args:
        **kwargs: keyword arguments to use for filling in template variables
                  in all the template messages in this chat template.

    Returns:
        list of formatted messages
    """
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
*In this example, the `format_messages` method formats the chat template into a list of finalized messages by resolving variables for each message template and collecting the formatted messages into a list.*

## Dependencies Used and Their Descriptions

### `logging`

- **Purpose:** Provides a way to configure and use loggers to output debug and other runtime information.
- **Usage in the File:**
  - Configures a logger for the module using `logging.getLogger(__name__)`.
  - Logs debug information about the resolved message content in the `format_messages` method.

### `typing`

- **Purpose:** Provides type hints for better code readability and type checking.
- **Usage in the File:**
  - Uses `Any`, `Dict`, and `List` for type annotations in function signatures.

### `jinja2`

- **Purpose:** A templating engine for Python used to create and render templates.
- **Usage in the File:**
  - Imports `Environment` and `DebugUndefined` to create and configure a Jinja2 environment for rendering templates.
  - Uses `Environment` to create a template from the message content and render it with `kwargs`.

### `langchain_core.prompts`

- **Purpose:** Provides core classes and functions for handling chat prompts.
- **Usage in the File:**
  - Imports `ChatPromptTemplate` as the base class for `Jinja2TemplatedChatMessagesTemplate`.

### `langchain_core.messages`

- **Purpose:** Provides core classes for different types of chat messages.
- **Usage in the File:**
  - Imports `BaseMessage`, `SystemMessage`, `AIMessage`, `HumanMessage`, and `ToolMessage` to handle different types of messages.

### `langchain_core.prompts.chat`

- **Purpose:** Provides core classes for handling chat message templates.
- **Usage in the File:**
  - Imports `BaseMessagePromptTemplate` and `BaseChatPromptTemplate` to handle different types of message templates.

## Functional Flow

The functional flow of the `chat_message_template.py` file involves the following steps:

1. **Class Initialization:** The `Jinja2TemplatedChatMessagesTemplate` class is initialized, inheriting from `ChatPromptTemplate`.
2. **Variable Resolution:** The `_resolve_variables` method is called to resolve template variables within a message using Jinja2.
3. **Message Formatting:** The `format_messages` method is called to format the chat template into a list of finalized messages by resolving variables for each message template and collecting the formatted messages into a list.
4. **Logging:** Debug information about the resolved message content is logged using the configured logger.

### Example:
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

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the chat template into a list of finalized messages.

        Args:
            **kwargs: keyword arguments to use for filling in template variables
                      in all the template messages in this chat template.

        Returns:
            list of formatted messages
        """
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
*In this example, the `Jinja2TemplatedChatMessagesTemplate` class defines the `_resolve_variables` and `format_messages` methods to resolve template variables and format the chat template into a list of finalized messages.*

## Endpoints Used/Created

The `chat_message_template.py` file does not explicitly define or call any endpoints. The primary focus of the file is on resolving template variables within chat messages and formatting them into a list of finalized messages using Jinja2 templates.