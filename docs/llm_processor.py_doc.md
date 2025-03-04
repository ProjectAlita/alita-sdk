# llm_processor.py

**Path:** `src/alita_sdk/langchain/interfaces/llm_processor.py`

## Data Flow

The data flow within `llm_processor.py` revolves around the processing and manipulation of language models, embeddings, and vector stores. The primary data elements include model types, model parameters, embeddings, documents, and vector store configurations. The data originates from function inputs, such as `model_type`, `model_params`, `embeddings_model`, `embeddings_params`, and documents. These inputs are transformed through various functions like `get_model`, `get_embeddings`, `summarize`, `llm_predict`, `get_vectorstore`, and `add_documents`.

For example, in the `get_model` function, the `model_type` and `model_params` are used to dynamically import and instantiate a language model:

```python
if model_type in llms:
    return get_llm(model_type)(**model_params)
```

Here, the `model_type` is checked against a list of available models (`llms`), and if found, the corresponding model is instantiated with the provided parameters (`model_params`). This demonstrates the flow of data from input parameters to the creation of a model instance.

## Functions Descriptions

### get_model

The `get_model` function is responsible for retrieving and instantiating a language model based on the provided `model_type` and `model_params`. It supports various model types, including preloaded models and custom models defined within the `langchain_community` package. The function dynamically imports the required model class and returns an instance of it.

### get_embeddings

The `get_embeddings` function retrieves and instantiates an embeddings model based on the provided `embeddings_model` and `embeddings_params`. Similar to `get_model`, it supports various embeddings models and dynamically imports the required class to create an instance.

### summarize

The `summarize` function generates a summary of a document using a specified language model (`llmodel`) and a summarization prompt. It checks the length of the document and applies the summarization prompt if the content length exceeds a certain threshold. The result is stored in the document's metadata.

### llm_predict

The `llm_predict` function uses a language model (`llmodel`) and a prompt to generate predictions based on the provided content. It creates a `PromptTemplate` from the prompt and uses an `LLMChain` to perform the prediction. The function handles errors and logs any failures during the prediction process.

### get_vectorstore

The `get_vectorstore` function retrieves and instantiates a vector store object based on the provided `vectorstore_type` and `vectorstore_params`. It supports various vector store types and dynamically imports the required class to create an instance. The function also allows for the inclusion of an embedding function if provided.

### add_documents

The `add_documents` function adds documents to a vector store. It extracts the text content and metadata from each document and adds them to the vector store using the `add_texts` method.

### generateResponse

The `generateResponse` function is responsible for generating a response based on the provided input, guidance message, context message, and other parameters. It retrieves embeddings, vector stores, and language models, and uses an `AlitaRetriever` to fetch relevant documents. The function constructs a context and messages for the language model to generate a response, which can be streamed or returned as a complete text.

## Dependencies Used and Their Descriptions

### importlib

The `importlib` module is used for dynamic import of modules and classes based on string names. This allows for flexible and dynamic loading of models and embeddings.

### traceback

The `traceback` module is used to format and log exceptions, providing detailed error information during the execution of functions like `llm_predict`.

### langchain.chains.llm.LLMChain

The `LLMChain` class from the `langchain` package is used to create a chain of language model operations, enabling the generation of predictions based on prompts.

### langchain_community.llms

The `langchain_community.llms` module provides access to various language models, allowing for dynamic retrieval and instantiation of models based on their names.

### langchain_community.chat_models

The `langchain_community.chat_models` module provides access to chat models, enabling the creation of conversational agents and chat-based interactions.

### langchain_community.embeddings

The `langchain_community.embeddings` module provides access to embeddings models, allowing for the generation of vector representations of text data.

### langchain_community.vectorstores

The `langchain_community.vectorstores` module provides access to vector store classes, enabling the storage and retrieval of vectorized text data.

### langchain.prompts.PromptTemplate

The `PromptTemplate` class from the `langchain.prompts` module is used to create templates for prompts, enabling the generation of structured input for language models.

### langchain.schema.HumanMessage, SystemMessage

The `HumanMessage` and `SystemMessage` classes from the `langchain.schema` module are used to represent messages in a conversational context, allowing for the construction of dialogue-based interactions.

### PreloadedEmbeddings, PreloadedChatModel

The `PreloadedEmbeddings` and `PreloadedChatModel` classes provide preloaded models for embeddings and chat interactions, enabling quick and efficient model instantiation.

### AlitaRetriever

The `AlitaRetriever` class is used to retrieve relevant documents from a vector store based on input queries, enabling the generation of context-aware responses.

### print_log

The `print_log` function is used for logging messages and errors, providing visibility into the execution flow and any issues encountered.

## Functional Flow

The functional flow of `llm_processor.py` involves the following steps:

1. **Model and Embeddings Retrieval:** Functions like `get_model` and `get_embeddings` are used to retrieve and instantiate language models and embeddings based on the provided parameters.
2. **Document Summarization:** The `summarize` function generates summaries for documents using a specified language model and summarization prompt.
3. **Prediction Generation:** The `llm_predict` function generates predictions based on a prompt and content using a language model.
4. **Vector Store Management:** Functions like `get_vectorstore` and `add_documents` manage the creation and population of vector stores with vectorized text data.
5. **Response Generation:** The `generateResponse` function generates responses based on input queries, context, and guidance messages, utilizing embeddings, vector stores, and language models.

For example, the `generateResponse` function orchestrates the entire process of generating a response:

```python
embedding = get_embeddings(embedding_model, embedding_model_params)
vectorstore_params['collection_name'] = collection
vs = get_vectorstore(vectorstore, vectorstore_params, embedding_func=embedding)
ai = get_model(ai_model, ai_model_params)
retriever = AlitaRetriever(
    vectorstore=vs,
    doc_library=collection,
    top_k = top_k,
    page_top_k=1,
    weights=weights
)
docs = retriever.invoke(input)
context = f'{guidance_message}\n\n'
references = set()
messages = []
for doc in docs[:top_k]:
    context += f'{doc.page_content}\n\n'
    references.add(doc.metadata["source"])
messages.append(SystemMessage(content=context_message))
messages.append(HumanMessage(content=context))
messages.append(HumanMessage(content=input))
if stream:
    return {
        "response_iterator": ai.stream(messages),
        "references": references
    }
response_text = ai.invoke(messages).content

return {
    "response": response_text,
    "references": references
}
```

## Endpoints Used/Created

The `llm_processor.py` file does not explicitly define or call any external endpoints. The functionality is focused on processing language models, embeddings, and vector stores, and generating responses based on input queries and context.