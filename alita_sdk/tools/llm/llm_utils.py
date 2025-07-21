from langchain_community.chat_models import __all__ as chat_models  # pylint: disable=E0401
from langchain_community.llms import __getattr__ as get_llm, __all__ as llms  # pylint: disable=E0401
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate


def get_model(model_type: str, model_params: dict):
    """ Get LLM or ChatLLM """
    if model_type is None:
        return None
    if model_type in llms:
        return get_llm(model_type)(**model_params)
    elif model_type in chat_models:
        model = getattr(__import__("langchain_community.chat_models", fromlist=[model_type]), model_type)
        return model(**model_params)
    raise RuntimeError(f"Unknown model type: {model_type}")


def summarize(llm, summarization_prompt: str, data_to_summarize: str, summarization_key: str):
    """ Summarize the passed data using the LLM or ChatLLM """
    if llm is None:
        return data_to_summarize
    prompt = PromptTemplate.from_template(summarization_prompt)
    chain = {summarization_key: lambda x: x} | prompt | llm | StrOutputParser()
    return chain.invoke(data_to_summarize)
