
from typing import Any, Optional
from langchain_core.messages import (
    HumanMessage,
)
from pydantic import create_model

class AlitaDataSource:
    def __init__(self, alita: Any, datasource_id: int, name: str, description: str,
                 datasource_settings, datasource_predict_settings):
        self.alita = alita
        self.name = name
        self.description = description
        self.datasource_id = datasource_id
        self.datasource_settings = datasource_settings
        self.datasource_predict_settings = datasource_predict_settings

    def predict(self, user_input: str, chat_history: Optional[list] = None):
        if chat_history is None:
            chat_history = []
        return self.alita.rag(datasource_id=self.datasource_id,
                              chat_history=chat_history,
                              user_input=user_input)

    def search(self, query: str):
        return self.alita.search(self.datasource_id, [HumanMessage(content=query)],
                                 self.datasource_settings)