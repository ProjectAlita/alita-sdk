# Copyright (c) 2023 Artem Rozumenko
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


#
#  This is adoption of https://github.com/langchain-ai/langchain/blob/master/libs/community/langchain_community/chat_models/openai.py
#

import logging
import requests
from time import sleep
from traceback import format_exc

from typing import Any, List, Optional, AsyncIterator, Dict, Iterator, Mapping, Type
from tiktoken import get_encoding, encoding_for_model
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel, SimpleChatModel
from langchain_core.messages import (AIMessageChunk, BaseMessage, HumanMessage, HumanMessageChunk, ChatMessageChunk, 
                                     FunctionMessageChunk, SystemMessageChunk, ToolMessageChunk, BaseMessageChunk)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import run_in_executor
from langchain_core.pydantic_v1 import Field, root_validator
from langchain_community.chat_models.openai import generate_from_stream, _convert_delta_to_message_chunk
from ..clients import AlitaClient

logger = logging.getLogger(__name__)


class MaxRetriesExceededError(Exception):
    """Raised when the maximum number of retries is exceeded"""
    
    def __init__(self, message="Maximum number of retries exceeded"):
        self.message = message
        super().__init__(self.message)


class AlitaChatModel(BaseChatModel):
    class Config:
        allow_population_by_field_name = True

    client: Any  #: :meta private:
    encoding: Any  #: :meta private:
    model_name: str = Field(default="gpt-35-turbo", alias="model")
    deployment: str = Field(default="https://eye.projectalita.ai", alias="base_url")
    api_token: str = Field(default=None, alias="api_key")
    project_id: int = None
    integration_uid: str = None
    max_tokens: Optional[int] = 512
    tiktoken_model_name: Optional[str] = None
    tiktoken_encoding_name: Optional[str] = 'cl100k_base'
    max_retries: int = 2
    temperature: float = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 20
    stream_response: Optional[bool] = Field(default=False, alias="stream")
    api_extra_headers: Optional[dict] = Field(default_factory=dict)
    configurations: Optional[list] = Field(default_factory=list)
    
    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        values['client'] = AlitaClient(
            values['deployment'], 
            values['project_id'], 
            values['api_token'], 
            api_extra_headers=values.get('api_extra_headers'),
            configurations=values.get('configurations', [])
        )
        if values["tiktoken_model_name"]:
            values["encoding"] = encoding_for_model(values["tiktoken_model_name"])
        else:
            values["encoding"] = get_encoding(values["tiktoken_encoding_name"])
        return values
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        
        # TODO: Implement streaming
        
        if self.stream_response:
            stream_iter = self._stream(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
            return generate_from_stream(stream_iter)
        self.stream_response = False
        response = self.completion_with_retry(messages)
        return self._create_chat_result(response)
    
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        
        self.stream_response = True
        default_chunk_class = AIMessageChunk
        for chunk in self.completion_with_retry(messages):
            if not isinstance(chunk, dict):
                chunk = chunk.dict()
            logger.debug(f"Chunk: {chunk}")
            if "delta" in chunk:
                chunk = _convert_delta_to_message_chunk(
                    chunk["delta"], default_chunk_class
                )
                finish_reason = chunk.get("z")
                generation_info = (
                    dict(finish_reason=finish_reason) if finish_reason is not None else None
                )
                default_chunk_class = chunk.__class__
                cg_chunk = ChatGenerationChunk(
                    message=chunk, generation_info=generation_info
                )
                if run_manager:
                    run_manager.on_llm_new_token(cg_chunk.text, chunk=cg_chunk)
                yield cg_chunk
            else:
                message = _convert_delta_to_message_chunk(chunk, default_chunk_class)
                finish_reason = None
                generation_info = ()
                if stop:
                    for stop_word in stop:
                        if stop_word in message.content:
                            finish_reason = "stop"
                            message.z = finish_reason
                            break
                    generation_info = (dict(finish_reason=finish_reason))
                logger.debug(f"message before getting to ChatGenerationChunk: {message}")
                yield ChatGenerationChunk(message=message, generation_info=generation_info)
    
    async def _astrem(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        raise NotImplementedError("Streaming is not implemented")
    
    def _create_chat_result(self, response: list[BaseMessage]) -> ChatResult:
        token_usage = 0
        generations = []
        for message in response:
            token_usage += len(self.encoding.encode(message.content))
            generations.append(ChatGeneration(message=message))
            
        llm_output = {
            "token_usage": token_usage,
            "model_name": self.model_name,
        }
        
        return ChatResult(
            generations=generations,
            llm_output=llm_output,
        )
            
    def completion_with_retry(self, messages, retry_count=0):
        try:
            return self.client.predict(messages, self._get_model_default_parameters)
        except requests.exceptions.HTTPError as e:
            logger.error(f"ERROR: Error in completion_with_retry: {e}, retry_count: {retry_count}")
            sleep(60)
            if retry_count >= self.max_retries:
                logger.error(f"ERROR: Retry count exceeded: {format_exc()}")
                raise MaxRetriesExceededError(format_exc())
            return self.completion_with_retry(messages, retry_count+1)
        except Exception as e:
            logger.error(f"ERROR: Error in completion_with_retry: {e}, retry_count: {retry_count}")
            if retry_count >= self.max_retries:
                logger.error(f"ERROR: Retry count exceeded: {format_exc()}")
                raise MaxRetriesExceededError(format_exc())
            return self.completion_with_retry(messages, retry_count+1)
    
    @property
    def _llm_type(self) -> str:
        """
        This should return the type of the LLM.
        """
        return self.model_name
    
    @property
    def _get_model_default_parameters(self):
        return  {
                "temperature": self.temperature,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "stream": self.stream_response,
                "model": {
                    "model_name": self.model_name,
                    "integration_uid": self.integration_uid,
                }
            }
    
    @property
    def _identifying_params(self) -> dict:
        """
        It should return a dict that provides the information of all the parameters 
        that are used in the LLM. This is useful when we print our llm, it will give use the 
        information of all the parameters.
        """
        return {
            "deployment": self.deployment,
            "api_token": self.api_token,
            "project_id": self.project_id,
            "integration_id": self.integration_uid,
            "model_settings": self._get_model_default_parameters,
        }

    
