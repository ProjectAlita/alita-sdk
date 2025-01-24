# preloaded.py

**Path:** `src/alita_sdk/llms/preloaded.py`

## Data Flow

The data flow within `preloaded.py` revolves around the interaction between the `PreloadedEmbeddings` and `PreloadedChatModel` classes and their respective methods. Data originates from the input parameters provided to these methods, such as texts for embedding or messages for generating chat responses. The data is then processed through various transformations and tasks managed by the `arbiter` library's `TaskNode` and `EventNode`.

For example, in the `embed_documents` method of `PreloadedEmbeddings`, the input texts are passed to the `start_task` method of `task_node`, which initiates a task to embed the documents. The task's result is then retrieved using the `join_task` method.

```python
# Example of data flow in embed_documents method

def embed_documents(self, texts):
    task_id = self.task_node.start_task(
        name="invoke_model",
        kwargs={
            "routing_key": self.model_name,
            "method": "embed_documents",
            "method_args": [texts],
            "method_kwargs": {},
        },
        pool="indexer",
    )
    return self.task_node.join_task(task_id)
```

In this example, the `texts` data is transformed into a task request, processed by the model, and the resulting embeddings are returned.

## Functions Descriptions

### `PreloadedEmbeddings.__init__`

The constructor initializes the `PreloadedEmbeddings` class with a model name and sets up the `EventNode` and `TaskNode` using the `arbiter` library. It configures the task node with specific parameters such as `pool`, `task_limit`, and `multiprocessing_context`.

### `PreloadedEmbeddings.embed_documents`

This method embeds a list of documents by starting a task with the `task_node`. It specifies the model method `embed_documents` and passes the texts as arguments. The task result, which contains the embeddings, is retrieved and returned.

### `PreloadedEmbeddings.embed_query`

Similar to `embed_documents`, this method embeds a single query text. It starts a task with the `task_node`, specifying the model method `embed_query` and passing the text as an argument. The task result is retrieved and returned.

### `PreloadedChatModel.__init__`

The constructor initializes the `PreloadedChatModel` class with various parameters such as `model_name`, `max_tokens`, and `temperature`. It sets up the `EventNode` and `TaskNode` and subscribes to stream events.

### `PreloadedChatModel._generate`

This method generates a chat response based on input messages. It maps the message roles, limits the tokens, and starts a task with the `task_node` to invoke the model. The generated text is then wrapped in an `AIMessage` and returned as a `ChatResult`.

### `PreloadedChatModel._stream`

This method streams chat responses by starting a task with the `task_node` to invoke the model in streaming mode. It handles stream events and yields `ChatGenerationChunk` objects as new tokens are generated.

## Dependencies Used and Their Descriptions

### `json`

Used for serializing and deserializing data to and from JSON format.

### `uuid`

Used for generating unique identifiers for stream sessions.

### `queue`

Used for managing queues in the streaming process.

### `pydantic.PrivateAttr`

Used for defining private attributes in the `PreloadedChatModel` class.

### `langchain_core`

Includes various modules such as `Embeddings`, `BaseChatModel`, `AIMessage`, and `ChatResult`, which are essential for embedding and chat functionalities.

### `arbiter`

Used for creating and managing event and task nodes, which handle the execution of model tasks.

### `tools.worker_core`

Provides configuration for the `EventNode` and `TaskNode`.

## Functional Flow

The functional flow in `preloaded.py` involves initializing the `PreloadedEmbeddings` and `PreloadedChatModel` classes, setting up the necessary nodes, and defining methods for embedding documents, embedding queries, generating chat responses, and streaming chat responses.

For instance, the `PreloadedChatModel._generate` method follows this flow:

1. Map message roles and limit tokens.
2. Start a task with the `task_node` to invoke the model.
3. Retrieve the generated text from the task result.
4. Wrap the generated text in an `AIMessage` and return it as a `ChatResult`.

## Endpoints Used/Created

The file does not explicitly define or call any external endpoints. Instead, it relies on the `arbiter` library's `TaskNode` and `EventNode` to manage tasks and events internally.
