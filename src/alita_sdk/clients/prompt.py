from typing import Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)
from pydantic import create_model

class AlitaPrompt:
    def __init__(self, alita: Any, prompt: ChatPromptTemplate, name: str, description: str, llm_settings: dict):
        self.alita = alita
        self.prompt = prompt
        self.name = name
        self.llm_settings = llm_settings
        self.description = description

    def create_pydantic_model(self):
        fields = {}
        for variable in self.prompt.input_variables:
            fields[variable] = (str, None)
        if "input" not in list(fields.keys()):
            fields["input"] = (str, None)
        return create_model("PromptVariables", **fields)

    def predict(self, variables: Optional[dict] = None):
        if variables is None:
            variables = {}
        user_input = variables.pop("input", '')
        alita_vars = []
        for key, value in variables.items():
            alita_vars.append({
                "name": key,
                "value": value
            })
        messages = [SystemMessage(content=self.prompt.messages[0].content), HumanMessage(content=user_input)]
        result = []
        for message in self.alita.predict(messages, self.llm_settings, variables=alita_vars):
            result.append(message.content)
        return "\n\n".join(result)