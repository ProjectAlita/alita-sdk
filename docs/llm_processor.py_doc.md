# llm_processor.py

**Path:** `src/alita_sdk/langchain/interfaces/llm_processor.py`

## Data Flow

The data flow within `llm_processor.py` revolves around the processing and transformation of data through various models and embeddings. The journey begins with the input data, which is processed by different functions to generate models, embeddings, and vector stores. The data is then used to generate responses, summaries, and predictions. The data flow can be summarized as follows:

1. **Input Data:** The input data is received by the functions, which include model types, model parameters, embeddings models, embeddings parameters, vector store types, and vector store parameters.
2. **Model Generation:** The `get_model` function generates models based on the input model type and parameters. It supports various models, including LLM, ChatLLM, PreloadedChatModel, and AlitaClient.
3. **Embeddings Generation:** The `get_embeddings` function generates embeddings based on the input embeddings model and parameters. It supports various embeddings models, including PreloadedEmbeddings and Chroma.
4. **Vector Store Generation:** The `get_vectorstore` function generates vector stores based on the input vector store type and parameters. It supports various vector stores and integrates embedding functions if provided.
5. **Data Processing:** The `summarize`, `llm_predict`, and `generateResponse` functions process the data using the generated models, embeddings, and vector stores. These functions perform tasks such as summarization, prediction, and response generation.
6. **Output Data:** The processed data is returned as output, which includes summaries, predictions, and responses.

Example:
```python
def get_model(model_type: str, model_params: dict):
    """ Get LLM or ChatLLM """
    if model_type is None:
        return None
    if "." in model_type:
        target_pkg, target_name = model_type.rsplit(".", 1)
        target_cls = getattr(
            importlib.import_module(target_pkg),
            target_name
        )
        return target_cls(**model_params)
    if model_type in llms:
        return get_llm(model_type)(**model_params)
    if model_type == "PreloadedChatModel":
        return PreloadedChatModel(**model_params)
    if model_type == "Alita":
        return AlitaClient(**model_params)
    if model_type in chat_models:
        model = getattr(
            __import__("langchain_community.chat_models", fromlist=[model_type]),
            model_type
        )
        return model(**model_params)
    raise RuntimeError(f"Unknown model type: {model_type}")
```

## Functions Descriptions

### `get_model`

The `get_model` function is responsible for generating models based on the input model type and parameters. It supports various models, including LLM, ChatLLM, PreloadedChatModel, and AlitaClient. The function takes two parameters: `model_type` (a string representing the type of model) and `model_params` (a dictionary of parameters for the model). The function returns an instance of the specified model.

### `get_embeddings`

The `get_embeddings` function generates embeddings based on the input embeddings model and parameters. It supports various embeddings models, including PreloadedEmbeddings and Chroma. The function takes two parameters: `embeddings_model` (a string representing the type of embeddings model) and `embeddings_params` (a dictionary of parameters for the embeddings model). The function returns an instance of the specified embeddings model.

### `summarize`

The `summarize` function generates a summary of a document using a specified language model and summarization prompt. It takes four parameters: `llmodel` (the language model to use), `document` (the document to summarize), `summorization_prompt` (the prompt to use for summarization), and `metadata_key` (a key to store the summary in the document's metadata). The function returns the summarized document.

### `llm_predict`

The `llm_predict` function generates a prediction using a specified language model and prompt. It takes three parameters: `llmodel` (the language model to use), `prompt` (the prompt to use for prediction), and `content` (the content to predict). The function returns the prediction result.

### `get_vectorstore`

The `get_vectorstore` function generates a vector store based on the input vector store type and parameters. It supports various vector stores and integrates embedding functions if provided. The function takes three parameters: `vectorstore_type` (a string representing the type of vector store), `vectorstore_params` (a dictionary of parameters for the vector store), and `embedding_func` (an optional embedding function). The function returns an instance of the specified vector store.

### `add_documents`

The `add_documents` function adds documents to a specified vector store. It takes two parameters: `vectorstore` (the vector store to add documents to) and `documents` (a list of documents to add). The function does not return a value.

### `generateResponse`

The `generateResponse` function generates a response based on the input data, guidance message, context message, and other parameters. It takes multiple parameters, including `input` (the input data), `guidance_message` (a guidance message), `context_message` (a context message), `collection` (a collection name), `top_k` (the number of top documents to retrieve), `ai_model` (the AI model to use), `ai_model_params` (parameters for the AI model), `embedding_model` (the embedding model to use), `embedding_model_params` (parameters for the embedding model), `vectorstore` (the vector store to use), `vectorstore_params` (parameters for the vector store), `weights` (weights for the retriever), and `stream` (a boolean indicating whether to stream the response). The function returns a dictionary containing the response and references.

## Dependencies Used and Their Descriptions

### `importlib`

The `importlib` module is used to import modules dynamically. It is used in the `get_model` and `get_embeddings` functions to import target classes based on the input model or embeddings type.

### `traceback`

The `traceback` module is used to format and print stack traces of exceptions. It is used in the `llm_predict` function to log errors when generating predictions.

### `langchain.chains.llm.LLMChain`

The `LLMChain` class from the `langchain.chains.llm` module is used to create a chain of language models for generating predictions. It is used in the `llm_predict` function to create an instance of the language model chain.

### `langchain_community.llms`

The `langchain_community.llms` module is used to get language models. It is used in the `get_model` function to get instances of language models based on the input model type.

### `langchain_community.chat_models`

The `langchain_community.chat_models` module is used to get chat models. It is used in the `get_model` function to get instances of chat models based on the input model type.

### `langchain_community.embeddings`

The `langchain_community.embeddings` module is used to get embeddings models. It is used in the `get_embeddings` function to get instances of embeddings models based on the input embeddings model.

### `langchain_community.vectorstores`

The `langchain_community.vectorstores` module is used to get vector store classes. It is used in the `get_vectorstore` function to get instances of vector stores based on the input vector store type.

### `langchain.prompts.PromptTemplate`

The `PromptTemplate` class from the `langchain.prompts` module is used to create prompt templates for language models. It is used in the `llm_predict` function to create an instance of the prompt template.

### `langchain.schema.HumanMessage`

The `HumanMessage` class from the `langchain.schema` module is used to create human messages for language models. It is used in the `generateResponse` function to create instances of human messages.

### `langchain.schema.SystemMessage`

The `SystemMessage` class from the `langchain.schema` module is used to create system messages for language models. It is used in the `generateResponse` function to create instances of system messages.

### `AlitaClient`

The `AlitaClient` class from the `...llms.alita` module is used to create instances of the Alita language model. It is used in the `get_model` function to get an instance of the Alita language model.

### `PreloadedEmbeddings`

The `PreloadedEmbeddings` class from the `...llms.preloaded` module is used to create instances of preloaded embeddings. It is used in the `get_embeddings` function to get an instance of preloaded embeddings.

### `PreloadedChatModel`

The `PreloadedChatModel` class from the `...llms.preloaded` module is used to create instances of preloaded chat models. It is used in the `get_model` function to get an instance of the preloaded chat model.

### `AlitaRetriever`

The `AlitaRetriever` class from the `..retrievers.AlitaRetriever` module is used to create instances of the Alita retriever. It is used in the `generateResponse` function to create an instance of the Alita retriever.

### `print_log`

The `print_log` function from the `..tools.log` module is used to log messages. It is used in the `llm_predict` function to log messages when generating predictions.

## Functional Flow

The functional flow of `llm_processor.py` involves the following sequence of operations:

1. **Model Generation:** The `get_model` function is called to generate models based on the input model type and parameters.
2. **Embeddings Generation:** The `get_embeddings` function is called to generate embeddings based on the input embeddings model and parameters.
3. **Vector Store Generation:** The `get_vectorstore` function is called to generate vector stores based on the input vector store type and parameters.
4. **Data Processing:** The `summarize`, `llm_predict`, and `generateResponse` functions are called to process the data using the generated models, embeddings, and vector stores. These functions perform tasks such as summarization, prediction, and response generation.
5. **Output Data:** The processed data is returned as output, which includes summaries, predictions, and responses.

Example:
```python
def generateResponse(
        input, guidance_message, context_message, collection, top_k=5,
        ai_model=None, ai_model_params=None,
        embedding_model=None, embedding_model_params=None,
        vectorstore=None, vectorstore_params=None,
        weights=None,
        stream=False,
    ):
    """ Deprecated """
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

The `llm_processor.py` file does not explicitly define or call any endpoints. The functionality is focused on processing data using language models, embeddings, and vector stores. The functions interact with these components to generate summaries, predictions, and responses based on the input data. There are no REST API calls or other types of endpoints defined within this file.