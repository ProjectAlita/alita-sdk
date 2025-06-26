#!/usr/bin/python3
# coding=utf-8

# Copyright (c) 2024 Artem Rozumenko
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

""" Preloaded models support """

import json
import uuid
import queue

from typing import Optional, Any

from pydantic import PrivateAttr  # pylint: disable=E0401

from langchain_core.embeddings import Embeddings  # pylint: disable=E0401
from langchain_core.language_models import BaseChatModel  # pylint: disable=E0401
from langchain_core.messages import AIMessage, AIMessageChunk  # pylint: disable=E0401
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult  # pylint: disable=E0401

try:
    from ..langchain.tools import log
except ImportError:
    import logging as _logging
    log = _logging.getLogger(__name__)


class PreloadedEmbeddings(Embeddings):
    """ Embeddings shim """

    def __init__(self, model_name, *args, **kwargs):  # pylint: disable=W0613
        self.model_name = model_name
        #
        import arbiter  # pylint: disable=E0401,C0415
        from tools import worker_core  # pylint: disable=E0401,C0415
        #
        # FIXME: should use multiprocessing_context to detect if clone is needed
        #
        self.event_node = arbiter.make_event_node(
            config=worker_core.event_node_config,
        )
        self.event_node.start()
        # TaskNode
        self.task_node = arbiter.TaskNode(
            self.event_node,
            pool="indexer",
            task_limit=0,
            ident_prefix="indexer_",
            multiprocessing_context="threading",
            kill_on_stop=False,
            task_retention_period=3600,
            housekeeping_interval=60,
            start_max_wait=3,
            query_wait=3,
            watcher_max_wait=3,
            stop_node_task_wait=3,
            result_max_wait=3,
        )
        self.task_node.start()

    def embed_documents(self, texts):
        """ Embed search docs """
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

    def embed_query(self, text):
        """ Embed query text """
        task_id = self.task_node.start_task(
            name="invoke_model",
            kwargs={
                "routing_key": self.model_name,
                "method": "embed_query",
                "method_args": [text],
                "method_kwargs": {},
            },
            pool="indexer",
        )
        return self.task_node.join_task(task_id)


class PreloadedChatModel(BaseChatModel):  # pylint: disable=R0903
    """ ChatModel shim """

    model_name: str = ""
    max_tokens: Optional[int] = 256
    temperature: Optional[float] = 0.9
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 20
    token_limit: Optional[int] = 1024

    _local_streams: Any = PrivateAttr()
    _event_node: Any = PrivateAttr()
    _task_node: Any = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #
        import arbiter  # pylint: disable=E0401,C0415
        from tools import worker_core  # pylint: disable=E0401,C0415
        # EventNode
        self._event_node = arbiter.make_event_node(
            config=worker_core.event_node_config,
        )
        self._event_node.start()
        # TaskNode
        self._task_node = arbiter.TaskNode(
            self._event_node,
            pool="indexer",
            task_limit=0,
            ident_prefix="indexer_",
            multiprocessing_context="threading",
            kill_on_stop=False,
            task_retention_period=3600,
            housekeeping_interval=60,
            start_max_wait=3,
            query_wait=3,
            watcher_max_wait=3,
            stop_node_task_wait=3,
            result_max_wait=3,
        )
        self._task_node.start()
        # Streaming
        self._local_streams = {}
        #
        def _on_stream_event(_, payload):
            event = payload.copy()
            stream_id = event.pop("stream_id", None)
            if stream_id not in self._local_streams:
                return
            self._local_streams[stream_id].put(event)
        #
        self._event_node.subscribe("stream_event", _on_stream_event)

    @staticmethod
    def _remove_non_system_messages(data, count):
        result = []
        removed = 0
        #
        for item in data:
            if item["role"] == "system":
                result.append(item)
                continue
            #
            if removed == count:
                result.append(item)
                continue
            #
            removed += 1
        #
        return result, removed

    @staticmethod
    def _count_tokens(data):
        import tiktoken  # pylint: disable=E0401,C0415
        encoding = tiktoken.get_encoding("cl100k_base")
        #
        result = 0
        #
        if isinstance(data, list):
            for item in data:
                result += len(encoding.encode(item["content"]))
        else:
            result += len(encoding.encode(data))
        #
        return result

    def _limit_tokens(self, data):
        #
        # input_tokens + max_new_tokens > token_limit:
        # - system message - always keep / check first, error on too big
        # - non-system: remove pairs (human/ai) until in limit
        # - check user input - how to return warnings / errors?
        #
        if not isinstance(data, list):
            return data  # FIXME: truncate text data too?
        #
        token_limit = self.token_limit
        #
        if token_limit is None:
            return data
        #
        if self.max_tokens is None:
            max_new_tokens = 0  # FIXME: just check input tokens?
        else:
            max_new_tokens = self.max_tokens
        #
        input_tokens = self._count_tokens(data)
        #
        if input_tokens + max_new_tokens <= token_limit:
            log.debug(f"Tokens: {input_tokens=}, {max_new_tokens=}, {token_limit=}")
            #
            return data
        #
        while True:
            data, removed = self._remove_non_system_messages(data, 2)
            #
            if removed == 0:  # FIXME: raise some error?
                break
            #
            input_tokens = self._count_tokens(data)
            #
            if input_tokens + max_new_tokens <= token_limit:
                break
        #
        log.debug(f"Tokens: {input_tokens=}, {max_new_tokens=}, {token_limit=}")
        #
        return data

    @property
    def _llm_type(self):
        return self.model_name

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # pylint: disable=W0613
        role_map = {
            "system": "system",
            "human": "user",
            "ai": "assistant",
        }
        #
        call_messages = json.loads(json.dumps([
            {
                "role": role_map.get(item.type, "user"),
                "content": item.content,
            } for item in messages
        ]))
        #
        call_messages = self._limit_tokens(call_messages)
        #
        call_kwargs = {
            "max_new_tokens": self.max_tokens,
            "return_full_text": False,
            "temperature": self.temperature,
            "do_sample": True,
            "top_k": self.top_k,
            "top_p": self.top_p,
        }
        #
        try:
            task_id = self._task_node.start_task(
                name="invoke_model",
                kwargs={
                    "routing_key": self.model_name,
                    "method": "__call__",
                    "method_args": [call_messages],
                    "method_kwargs": call_kwargs,
                },
                pool="indexer",
            )
            #
            task_result = self._task_node.join_task(task_id)
        except:  # pylint: disable=W0702
            log.exception("Exception from invoke_model")
            raise
        #
        generated_text = task_result[0]["generated_text"]
        #
        message = AIMessage(content=generated_text)
        generation = ChatGeneration(message=message)
        result = ChatResult(generations=[generation])
        #
        return result

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):  # pylint: disable=W0613
        role_map = {
            "system": "system",
            "human": "user",
            "ai": "assistant",
        }
        #
        call_messages = json.loads(json.dumps([
            {
                "role": role_map.get(item.type, "user"),
                "content": item.content,
            } for item in messages
        ]))
        #
        call_messages = self._limit_tokens(call_messages)
        #
        call_kwargs = {
            "max_new_tokens": self.max_tokens,
            "return_full_text": False,
            "temperature": self.temperature,
            "do_sample": True,
            "top_k": self.top_k,
            "top_p": self.top_p,
        }
        #
        while True:
            stream_id = str(uuid.uuid4())
            if stream_id not in self._local_streams:
                break
        #
        self._local_streams[stream_id] = queue.Queue()
        #
        try:
            task_id = self._task_node.start_task(
                name="invoke_model",
                kwargs={
                    "routing_key": self.model_name,
                    "method": "stream",
                    "method_args": [call_messages],
                    "method_kwargs": call_kwargs,
                    "stream_id": stream_id,
                    "block": False,
                },
                pool="indexer",
            )
            #
            self._task_node.join_task(task_id)
        except:  # pylint: disable=W0702
            log.exception("Exception from invoke_model")
            raise
        #
        while True:
            event = self._local_streams[stream_id].get()
            #
            event_type = event.get("type", None)
            event_data = event.get("data", None)
            #
            if event_type == "stream_end":
                break
            #
            if event_type == "stream_chunk":
                message_chunk = AIMessageChunk(content=event_data)
                generation_chunk = ChatGenerationChunk(message=message_chunk)
                #
                if run_manager:
                    run_manager.on_llm_new_token(event_data, chunk=generation_chunk)
                #
                yield generation_chunk
        #
        self._local_streams.pop(stream_id, None)
