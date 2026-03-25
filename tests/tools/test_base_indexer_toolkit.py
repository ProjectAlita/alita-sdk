"""
Pytest tests for BaseIndexerToolkit search_index functionality.

This test suite validates the search_index tool with various filter configurations
using a pre-populated pgvector database. It uses DeepEval's multi-turn RAG evaluation
metrics to assess retrieval quality.

Prerequisites:
  - pgvector running with test data
  - Valid Alita credentials in environment

Setup:
  1. Set environment variables:
       export DEPLOYMENT_URL=https://dev.elitea.ai
       export ALITA_API_KEY=your_api_key
       export PROJECT_ID=your_project_id
       export DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS=gpt-4o-mini  # optional

  2. Start pgvector and load test data:
       ./tests/tools/fixtures/pgvector/setup_pgvector.sh

  3. Run tests:
       pytest tests/tools/test_base_indexer_toolkit.py -v

Skip behavior:
  - Tests will skip if credentials are not set (no default values)
  - Tests will skip if pgvector is not running or has no test data
  - Tests will skip if AlitaClient initialization fails

Run:
  pytest tests/tools/test_base_indexer_toolkit.py -v
  pytest tests/tools/test_base_indexer_toolkit.py -v -k "multi_turn"
  pytest tests/tools/test_base_indexer_toolkit.py -v -m "rag_eval"
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import SecretStr
from alita_sdk.runtime.clients.client import AlitaClient
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit
from deepeval.test_case import LLMTestCase, ConversationalTestCase, Turn
from deepeval.metrics import (
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)
from deepeval.models import DeepEvalBaseLLM

# Import multi-turn metrics
from deepeval.metrics import ConversationalGEval, KnowledgeRetentionMetric
from deepeval.test_case.conversational_test_case import TurnParams


class LangChainDeepEvalModel(DeepEvalBaseLLM):
    """Custom DeepEval model wrapper for LangChain LLMs (e.g., Alita).

    Implements DeepEval's expected interface for custom LLM integration.
    Forces DeepEval to use our generate methods instead of native API calls.
    """

    def __init__(self, langchain_llm):
        """Wrap a LangChain LLM for use with DeepEval.

        Args:
            langchain_llm: LangChain LLM instance (e.g., ChatAnthropic from Alita)
        """
        self._langchain_llm = langchain_llm  # Use private attr to hide from DeepEval

        # Use a generic model name to prevent DeepEval from special-casing
        if hasattr(langchain_llm, 'model_name'):
            self._model_name = langchain_llm.model_name
        elif hasattr(langchain_llm, 'model'):
            self._model_name = langchain_llm.model
        else:
            self._model_name = langchain_llm.__class__.__name__

    def _clean_json(self, json_str: str) -> str:
        """Clean common JSON formatting issues from LLM responses."""
        import re
        # Remove trailing commas before ] or }
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        return json_str

    def _repair_json(self, json_str: str, schema):
        """Attempt to repair and parse malformed JSON."""
        import json

        # First try direct parsing
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Try with json_repair if available
        try:
            from json_repair import repair_json
            repaired = repair_json(json_str)
            return json.loads(repaired)
        except ImportError:
            pass
        except Exception:
            pass

        # Manual repair: try to extract key fields based on schema
        # This is a fallback for when LLM generates malformed JSON with unescaped quotes
        try:
            # For DeepEval schemas, extract the essential list fields
            if hasattr(schema, '__annotations__'):
                for field_name in schema.__annotations__:
                    # Try to find the field content using regex
                    pattern = rf'"{field_name}":\s*\[(.*?)\]'
                    match = re.search(pattern, json_str, re.DOTALL)
                    if match:
                        # Found the array content - try to parse items individually
                        items_str = match.group(1)
                        # Split by }, { to get individual items
                        items = []
                        item_matches = re.finditer(r'\{[^{}]*\}', items_str)
                        for item_match in item_matches:
                            try:
                                item = json.loads(item_match.group())
                                items.append(item)
                            except:
                                # Skip malformed items
                                continue
                        if items:
                            return {field_name: items}
        except Exception:
            pass

        raise json.JSONDecodeError("Could not repair JSON", json_str, 0)

    def generate(self, prompt: str, schema=None):
        """Generate response using LangChain LLM.

        Args:
            prompt: The prompt to send to the LLM
            schema: Optional Pydantic schema for structured output
        """
        from langchain_core.messages import HumanMessage
        import json
        import re

        response = self._langchain_llm.invoke([HumanMessage(content=prompt)])
        content = response.content

        if schema is not None:
            # Parse JSON from response and construct Pydantic model
            # Find JSON in response (may be wrapped in markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # Try to find raw JSON
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end] if start != -1 and end > 0 else content

            # Clean common JSON issues
            json_str = self._clean_json(json_str)

            try:
                data = self._repair_json(json_str, schema)
                return schema(**data)
            except json.JSONDecodeError as e:
                # Check if response was truncated (common with token limits)
                if not json_str.rstrip().endswith('}'):
                    raise ValueError(
                        f"LLM response was truncated (likely token limit). "
                        f"Schema: {schema.__name__}, Last 100 chars: ...{json_str[-100:]}"
                    )
                raise ValueError(f"Failed to parse LLM response as {schema.__name__}: {e}\nJSON: {json_str[:500]}")
            except Exception as e:
                raise ValueError(f"Failed to construct {schema.__name__}: {e}\nJSON: {json_str[:500]}")

        return content

    async def a_generate(self, prompt: str, schema=None):
        """Async generate response using LangChain LLM.

        Args:
            prompt: The prompt to send to the LLM
            schema: Optional Pydantic schema for structured output
        """
        from langchain_core.messages import HumanMessage
        import json
        import re

        response = await self._langchain_llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content

        if schema is not None:
            # Parse JSON from response and construct Pydantic model
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end] if start != -1 and end > 0 else content

            # Clean common JSON issues
            json_str = self._clean_json(json_str)

            try:
                data = self._repair_json(json_str, schema)
                return schema(**data)
            except json.JSONDecodeError as e:
                if not json_str.rstrip().endswith('}'):
                    raise ValueError(
                        f"LLM response was truncated. Schema: {schema.__name__}, Last 100 chars: ...{json_str[-100:]}"
                    )
                raise ValueError(f"Failed to parse LLM response as {schema.__name__}: {e}\nJSON: {json_str[:500]}")
            except Exception as e:
                raise ValueError(f"Failed to construct {schema.__name__}: {e}\nJSON: {json_str[:500]}")

        return content

    def get_model_name(self) -> str:
        """Return model name for logging."""
        return self._model_name

    def load_model(self):
        """DeepEval interface - return None to force using generate methods."""
        return None


# Test configuration
PGVECTOR_CONNECTION_STRING = os.getenv(
    "PGVECTOR_TEST_CONNECTION_STRING",
    "postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"
)
# Collection schema matches the schema name in pgvector where data is stored
TEST_COLLECTION_NAME = "index_chunks"
# Index name matches the 'collection' field in cmetadata
TEST_INDEX_NAME = "three_in_one"

# Required environment variables (no defaults - must be explicitly set)
DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL")
API_KEY = os.getenv("ALITA_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS", "gpt-4o-mini")
# DeepEval metrics model (defaults to OpenAI model since Anthropic has auth issues with LiteLLM)
DEEPEVAL_LLM_MODEL = os.getenv("DEEPEVAL_LLM_MODEL", "gpt-4o-mini")

# ===================== DeepEval Threshold Constants =====================
# Thresholds define the minimum acceptable score for each metric type.
# metric.success = (metric.score >= threshold)
#
# Threshold guidelines:
#   0.3-0.5: Exploratory/development testing (lenient)
#   0.5-0.7: Integration testing (moderate)
#   0.7-0.8: Production readiness (strict)
#   0.8-1.0: High-stakes applications (very strict)

# Single-turn metric thresholds
THRESHOLD_FAITHFULNESS = 0.5          # Response grounded in context (no hallucinations)
THRESHOLD_CONTEXTUAL_RELEVANCY = 0.3  # Retrieved context is relevant to query
THRESHOLD_CONTEXTUAL_PRECISION = 0.3  # Most relevant docs ranked higher
THRESHOLD_CONTEXTUAL_RECALL = 0.3     # Context contains info needed to answer

# Multi-turn conversation thresholds
THRESHOLD_TURN_FAITHFULNESS = 0.5     # Each turn grounded in its context
THRESHOLD_TURN_RELEVANCY = 0.3        # Turn context relevant to conversation
THRESHOLD_RESPONSE_QUALITY = 0.3      # Responses adequately address questions

# Edge case thresholds (more lenient for boundary testing)
THRESHOLD_EDGE_CASE = 0.0             # Just verify metric runs without error


def _check_credentials_available() -> bool:
    """Check if all required credentials are available."""
    return all([DEPLOYMENT_URL, PROJECT_ID, API_KEY])


def _check_embedding_credentials_available() -> bool:
    """Check if embedding API credentials are available via Alita or OpenAI."""
    # Alita client handles embeddings via its own API, so we only need Alita credentials
    # OPENAI_API_KEY is not required when using Alita's embedding service
    return _check_credentials_available()


@pytest.fixture(scope="module")
def alita_client():
    """Create AlitaClient instance for tests.

    Requires environment variables:
    - DEPLOYMENT_URL: Alita deployment URL
    - PROJECT_ID: Project ID
    - ALITA_API_KEY: API key
    """
    if not _check_credentials_available():
        pytest.skip("Required credentials not available (DEPLOYMENT_URL, PROJECT_ID, ALITA_API_KEY)")

    try:
        client = AlitaClient(
            base_url=DEPLOYMENT_URL,
            project_id=int(PROJECT_ID),
            auth_token=SecretStr(API_KEY),
        )
        return client
    except Exception as e:
        pytest.skip(f"Failed to create AlitaClient: {e}")


@pytest.fixture(scope="module")
def indexer_toolkit(alita_client):
    """Create BaseIndexerToolkit instance for tests.

    This fixture requires:
    - Valid Alita credentials (DEPLOYMENT_URL, PROJECT_ID, ALITA_API_KEY)
    - Running pgvector database at PGVECTOR_TEST_CONNECTION_STRING
    """
    if not _check_embedding_credentials_available():
        pytest.skip("Alita credentials not set (required for embeddings)")

    try:
        # Get LLM from the client
        llm = alita_client.get_llm(
            model_name=DEFAULT_LLM_MODEL,
            model_config={"temperature": 0},
        )

        # Embedding model must match what was used to create the index
        # The test data was indexed with text-embedding-ada-002
        embedding_model = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-ada-002")

        toolkit = BaseIndexerToolkit(
            alita=alita_client,
            llm=llm,
            embedding_model=embedding_model,
            connection_string=PGVECTOR_CONNECTION_STRING,
            collection_schema=TEST_COLLECTION_NAME,
        )

        # Validate the toolkit can connect
        toolkit._ensure_vectorstore_initialized()

        return toolkit
    except Exception as e:
        pytest.skip(f"Failed to create BaseIndexerToolkit (check env vars and pgvector): {e}")


@pytest.fixture(scope="module")
def deepeval_model(alita_client):
    """Create DeepEval model wrapper using Alita LLM.

    This wraps the Alita LLM for use with DeepEval metrics.
    Uses DEEPEVAL_LLM_MODEL (defaults to gpt-4o-mini) since Anthropic models
    have auth issues with Alita's LiteLLM proxy.
    """
    try:
        llm = alita_client.get_llm(
            model_name=DEEPEVAL_LLM_MODEL,
            model_config={
                "temperature": 0,
                "max_tokens": 4096,  # Increase for DeepEval's structured output
            },
        )
        return LangChainDeepEvalModel(llm)
    except Exception as e:
        pytest.skip(f"Failed to create DeepEval model: {e}")


# ===================== Helper Functions =====================

def search_and_extract_context(toolkit, query: str, index_name: str = TEST_INDEX_NAME, cut_off: float = 0.1) -> tuple[str, List[str]]:
    """
    Execute search and extract retrieval context.

    Args:
        toolkit: BaseIndexerToolkit instance
        query: Search query
        index_name: Index to search in
        cut_off: Similarity threshold (0.0 returns all results, useful for test data with random embeddings)

    Returns:
        Tuple of (actual_output, retrieval_context_list)
    """
    response = toolkit.search_index(query=query, index_name=index_name, cut_off=cut_off, search_top=5)

    if isinstance(response, list) and response:
        # Handle both dict format and Document format
        retrieval_context = []
        for doc in response:
            if isinstance(doc, dict):
                content = doc.get('page_content') or doc.get('content') or doc.get('text') or str(doc)
            else:
                content = getattr(doc, 'page_content', None) or str(doc)
            retrieval_context.append(content)
        actual_output = "\n".join(retrieval_context)
    elif isinstance(response, str):
        retrieval_context = [response]
        actual_output = response
    else:
        retrieval_context = [str(response)]
        actual_output = str(response)

    return actual_output, retrieval_context


# ===================== Test Data Definitions =====================
# Test scenarios for Claude Certified Architect exam content
# Focused on allowedTools configuration and candidate requirements

# Scenario 1: allowedTools Configuration Queries
# Tests retrieval of tool access and configuration documentation
ALLOWED_TOOLS_CONVERSATION = {
    "expected_outcome": "User understands allowedTools configuration for subagents and skills",
    "turns": [
        {
            "role": "user",
            "content": "What is allowedTools and how do I configure it for subagents?",
            "expected_topics": ["allowedTools", "Task", "subagent", "coordinator"],
        },
        {
            "role": "user",
            "content": "How do I restrict tool access in skill frontmatter?",
            "expected_topics": ["allowed-tools", "skill", "frontmatter", "restrict"],
        },
        {
            "role": "user",
            "content": "What tools must be included for a coordinator to spawn subagents?",
            "expected_topics": ["Task tool", "spawning", "coordinator", "subagents"],
        },
    ],
}

# Scenario 2: Candidate Requirements Queries
# Tests retrieval of exam candidate information
CANDIDATE_REQUIREMENTS_CONVERSATION = {
    "expected_outcome": "User understands certification candidate requirements and exam content",
    "turns": [
        {
            "role": "user",
            "content": "What experience should a candidate have for the Claude Architect certification?",
            "expected_topics": ["candidate", "experience", "6+ months", "Agent SDK"],
        },
        {
            "role": "user",
            "content": "What skills should candidates demonstrate?",
            "expected_topics": ["agentic applications", "multi-agent", "MCP", "prompts"],
        },
        {
            "role": "user",
            "content": "What are the exam content domains and weightings?",
            "expected_topics": ["Domain", "Agentic Architecture", "Tool Design", "weightings"],
        },
    ],
}

# Scenario 3: Multi-Agent Architecture Queries
# Tests retrieval of orchestration and coordination patterns
MULTI_AGENT_CONVERSATION = {
    "expected_outcome": "User learns about multi-agent coordination patterns",
    "turns": [
        {
            "role": "user",
            "content": "How do I pass context between agents in a multi-agent system?",
            "expected_topics": ["context", "subagent", "prompt", "coordinator"],
        },
        {
            "role": "user",
            "content": "What is the best way to handle errors in subagent communication?",
            "expected_topics": ["error", "propagation", "recovery", "structured"],
        },
        {
            "role": "user",
            "content": "How should I partition research scope across subagents?",
            "expected_topics": ["partition", "scope", "subagents", "duplication"],
        },
    ],
}


# ===================== Single-Turn RAG Tests =====================

@pytest.mark.rag_eval
class TestSingleTurnRAGEvaluation:
    """Single-turn RAG evaluation tests for Claude Architect exam content."""

    def test_faithfulness_allowed_tools(self, indexer_toolkit, deepeval_model):
        """
        Test faithfulness for allowedTools configuration queries.

        Faithfulness measures whether the actual output is grounded in the
        retrieval context (no hallucinations).
        """
        query = "What is allowedTools and when must it include the Task tool?"
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        metric = FaithfulnessMetric(threshold=THRESHOLD_FAITHFULNESS, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nFaithfulness Test (allowedTools):")
        print(f"  Query: {query}")
        print(f"  Score: {metric.score} (threshold: {THRESHOLD_FAITHFULNESS})")
        print(f"  Reason: {metric.reason}")

        assert metric.success, f"Faithfulness failed: {metric.score} < {THRESHOLD_FAITHFULNESS}. Reason: {metric.reason}"

    def test_contextual_relevancy_candidate(self, indexer_toolkit, deepeval_model):
        """
        Test contextual relevancy for candidate requirements queries.

        Contextual Relevancy measures whether the retrieval context aligns
        with what the user is asking about.
        """
        query = "What qualifications should a candidate have for the Claude Architect certification?"
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        metric = ContextualRelevancyMetric(threshold=THRESHOLD_CONTEXTUAL_RELEVANCY, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nContextual Relevancy Test (candidate):")
        print(f"  Query: {query}")
        print(f"  Score: {metric.score} (threshold: {THRESHOLD_CONTEXTUAL_RELEVANCY})")
        print(f"  Reason: {metric.reason}")

        assert metric.success, f"Contextual Relevancy failed: {metric.score} < {THRESHOLD_CONTEXTUAL_RELEVANCY}. Reason: {metric.reason}"

    def test_contextual_precision_subagent_config(self, indexer_toolkit, deepeval_model):
        """
        Test contextual precision for subagent configuration queries.

        Contextual Precision measures whether the most relevant documents
        appear at the top of the retrieval results.
        """
        query = "How do I configure subagent invocation and context passing?"
        expected_output = "Subagent context must be explicitly provided in the prompt. Use Task tool for spawning subagents."
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=retrieval_context,
        )

        metric = ContextualPrecisionMetric(threshold=THRESHOLD_CONTEXTUAL_PRECISION, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nContextual Precision Test (subagent config):")
        print(f"  Query: {query}")
        print(f"  Score: {metric.score} (threshold: {THRESHOLD_CONTEXTUAL_PRECISION})")
        print(f"  Reason: {metric.reason}")

        assert metric.success, f"Contextual Precision failed: {metric.score} < {THRESHOLD_CONTEXTUAL_PRECISION}. Reason: {metric.reason}"

    def test_contextual_recall_exam_domains(self, indexer_toolkit, deepeval_model):
        """
        Test contextual recall for exam domain queries.

        Contextual Recall measures whether the retrieval context contains
        all the information needed to answer the query.
        """
        query = "What are the exam content domains and their weightings?"
        expected_output = "Domain 1: Agentic Architecture (27%), Domain 2: Tool Design & MCP (18%), Domain 3: Claude Code (20%), Domain 4: Prompt Engineering (20%), Domain 5: Context Management (15%)"
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=retrieval_context,
        )

        metric = ContextualRecallMetric(threshold=THRESHOLD_CONTEXTUAL_RECALL, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nContextual Recall Test (exam domains):")
        print(f"  Query: {query}")
        print(f"  Score: {metric.score} (threshold: {THRESHOLD_CONTEXTUAL_RECALL})")
        print(f"  Reason: {metric.reason}")

        assert metric.success, f"Contextual Recall failed: {metric.score} < {THRESHOLD_CONTEXTUAL_RECALL}. Reason: {metric.reason}"


# ===================== Multi-Turn Conversational RAG Tests =====================

@pytest.mark.rag_eval
class TestMultiTurnRAGEvaluation:
    """
    Multi-turn RAG evaluation tests using DeepEval's ConversationalTestCase.

    These tests simulate real conversational interactions where context
    from previous turns may influence retrieval and responses.
    """

    def test_multi_turn_allowed_tools_conversation(self, indexer_toolkit, deepeval_model):
        """
        Test a multi-turn conversation about allowedTools configuration.

        This simulates a user learning about tool access configuration:
        1. Ask about allowedTools basics
        2. Ask about skill frontmatter restrictions
        3. Ask about coordinator requirements

        Uses ConversationalGEval with custom criteria for RAG evaluation.
        """
        conversation_data = ALLOWED_TOOLS_CONVERSATION
        turns = []

        for turn_data in conversation_data["turns"]:
            query = turn_data["content"]
            actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

            # User turn
            turns.append(Turn(role="user", content=query))

            # Assistant turn with retrieval context
            turns.append(Turn(
                role="assistant",
                content=actual_output,
                retrieval_context=retrieval_context,
            ))

        # Create conversational test case
        convo_test_case = ConversationalTestCase(turns=turns)

        print(f"\n{'='*60}")
        print(f"Multi-Turn Conversation: Python Testing")
        print(f"Expected Outcome: {conversation_data['expected_outcome']}")
        print(f"{'='*60}")

        # Use ConversationalGEval for multi-turn RAG evaluation
        # Define custom metrics for RAG quality using correct TurnParams
        rag_metrics = [
            ConversationalGEval(
                name="Turn Faithfulness",
                criteria="Evaluate whether each assistant response is factually grounded in its retrieval context. "
                         "The response should not contain information not present in the retrieved documents.",
                evaluation_params=[TurnParams.CONTENT, TurnParams.RETRIEVAL_CONTEXT],
                threshold=THRESHOLD_TURN_FAITHFULNESS,
                model=deepeval_model,
                async_mode=False,
            ),
            ConversationalGEval(
                name="Turn Contextual Relevancy",
                criteria="Evaluate whether the retrieved context for each turn is relevant to the conversation. "
                         "The retrieval context should contain information that helps answer the user's question.",
                evaluation_params=[TurnParams.CONTENT, TurnParams.RETRIEVAL_CONTEXT],
                threshold=THRESHOLD_TURN_RELEVANCY,
                model=deepeval_model,
                async_mode=False,
            ),
            ConversationalGEval(
                name="Response Quality",
                criteria="Evaluate whether the assistant's responses adequately address the user's questions "
                         "using information from the retrieval context. Check for completeness and accuracy.",
                evaluation_params=[TurnParams.CONTENT, TurnParams.RETRIEVAL_CONTEXT],
                threshold=THRESHOLD_RESPONSE_QUALITY,
                model=deepeval_model,
                async_mode=False,
            ),
        ]

        results = {}
        failures = []
        for metric in rag_metrics:
            metric.measure(convo_test_case)
            results[metric.name] = {"score": metric.score, "success": metric.success, "threshold": metric.threshold}
            status = "PASS" if metric.success else "FAIL"
            print(f"  {metric.name}: {metric.score:.2f} (threshold: {metric.threshold}) [{status}]")
            if hasattr(metric, 'reason') and metric.reason:
                print(f"    Reason: {metric.reason[:100]}...")
            if not metric.success:
                failures.append(f"{metric.name}: {metric.score} < {metric.threshold}")

        # Assert all metrics pass their thresholds
        assert not failures, f"Multi-turn metrics failed: {'; '.join(failures)}"

    def test_multi_turn_candidate_requirements(self, indexer_toolkit, deepeval_model):
        """
        Test multi-turn conversation about candidate requirements.

        This tests contextual understanding across turns where each question
        builds on the previous context about exam preparation.
        """
        turns = []

        # Turn 1: Initial query about candidate experience
        query1 = "What experience should a candidate have for the Claude Architect certification?"
        actual_output1, retrieval_context1 = search_and_extract_context(
            indexer_toolkit, query1
        )
        turns.extend([
            Turn(role="user", content=query1),
            Turn(role="assistant", content=actual_output1, retrieval_context=retrieval_context1),
        ])

        # Turn 2: Follow-up about skills
        query2 = "What specific skills should the candidate demonstrate?"
        actual_output2, retrieval_context2 = search_and_extract_context(
            indexer_toolkit, query2
        )
        turns.extend([
            Turn(role="user", content=query2),
            Turn(role="assistant", content=actual_output2, retrieval_context=retrieval_context2),
        ])

        # Turn 3: Ask about exam content
        query3 = "What are the exam domains and how is it scored?"
        actual_output3, retrieval_context3 = search_and_extract_context(
            indexer_toolkit, query3
        )
        turns.extend([
            Turn(role="user", content=query3),
            Turn(role="assistant", content=actual_output3, retrieval_context=retrieval_context3),
        ])

        convo_test_case = ConversationalTestCase(turns=turns)

        # Use ConversationalGEval for faithfulness evaluation
        metric = ConversationalGEval(
            name="Conversation Faithfulness",
            criteria="Evaluate whether assistant responses are grounded in the retrieval context "
                     "and do not hallucinate information not present in the retrieved documents.",
            evaluation_params=[TurnParams.CONTENT, TurnParams.RETRIEVAL_CONTEXT],
            threshold=THRESHOLD_TURN_FAITHFULNESS,
            model=deepeval_model,
            async_mode=False,
        )
        metric.measure(convo_test_case)

        status = "PASS" if metric.success else "FAIL"
        print(f"\nMulti-Turn with Follow-ups:")
        print(f"  Faithfulness Score: {metric.score:.2f} (threshold: {THRESHOLD_TURN_FAITHFULNESS}) [{status}]")
        if hasattr(metric, 'reason') and metric.reason:
            print(f"  Reason: {metric.reason[:150]}...")

        assert metric.success, f"Conversation Faithfulness failed: {metric.score} < {THRESHOLD_TURN_FAITHFULNESS}. Reason: {metric.reason}"

    def test_comprehensive_rag_evaluation(self, indexer_toolkit, deepeval_model):
        """
        Comprehensive RAG evaluation testing all metrics across Claude Architect exam content.

        This test provides a thorough evaluation of RAG quality by testing
        allowedTools, candidate requirements, and multi-agent architecture queries.
        """
        # Define comprehensive test queries with expected outputs
        test_queries = [
            {
                "query": "What is allowedTools and when must Task be included?",
                "expected": "allowedTools must include Task for a coordinator to invoke subagents",
                "category": "allowed_tools",
            },
            {
                "query": "How do I restrict tool access in skill frontmatter?",
                "expected": "Configure allowed-tools in skill frontmatter to restrict tool access during skill execution",
                "category": "skill_config",
            },
            {
                "query": "What experience should a candidate have for the certification?",
                "expected": "Candidate should have 6+ months of practical experience with Claude APIs, Agent SDK, Claude Code, and MCP",
                "category": "candidate_requirements",
            },
            {
                "query": "How do I pass context between agents in a multi-agent system?",
                "expected": "Subagent context must be explicitly provided in the prompt. Include complete findings from prior agents directly in the subagent's prompt.",
                "category": "multi_agent",
            },
            {
                "query": "What are the exam content domains and weightings?",
                "expected": "Domain 1: Agentic Architecture (27%), Domain 2: Tool Design & MCP (18%), Domain 3: Claude Code (20%), Domain 4: Prompt Engineering (20%), Domain 5: Context Management (15%)",
                "category": "exam_domains",
            },
        ]

        all_results = []

        print(f"\n{'='*70}")
        print("COMPREHENSIVE RAG EVALUATION")
        print(f"{'='*70}")

        for test_data in test_queries:
            query = test_data["query"]
            expected = test_data["expected"]
            category = test_data["category"]

            actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

            test_case = LLMTestCase(
                input=query,
                actual_output=actual_output,
                expected_output=expected,
                retrieval_context=retrieval_context,
            )

            # Evaluate with all metrics using constants
            metrics = {
                "Faithfulness": FaithfulnessMetric(threshold=THRESHOLD_FAITHFULNESS, model=deepeval_model, async_mode=False),
                "Relevancy": ContextualRelevancyMetric(threshold=THRESHOLD_CONTEXTUAL_RELEVANCY, model=deepeval_model, async_mode=False),
                "Precision": ContextualPrecisionMetric(threshold=THRESHOLD_CONTEXTUAL_PRECISION, model=deepeval_model, async_mode=False),
                "Recall": ContextualRecallMetric(threshold=THRESHOLD_CONTEXTUAL_RECALL, model=deepeval_model, async_mode=False),
            }

            scores = {}
            successes = {}
            for name, metric in metrics.items():
                metric.measure(test_case)
                scores[name] = metric.score
                successes[name] = metric.success

            all_results.append({
                "query": query,
                "category": category,
                "scores": scores,
                "successes": successes,
                "context_count": len(retrieval_context),
            })

            print(f"\n[{category.upper()}] {query[:50]}...")
            print(f"  Context chunks retrieved: {len(retrieval_context)}")
            for name, score in scores.items():
                status = "PASS" if successes[name] else "FAIL"
                print(f"  {name}: {score:.2f} [{status}]")

        # Summary statistics
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")

        metric_names = ["Faithfulness", "Relevancy", "Precision", "Recall"]
        avg_scores = {
            metric: sum(r["scores"][metric] for r in all_results) / len(all_results)
            for metric in metric_names
        }
        pass_rates = {
            metric: sum(1 for r in all_results if r["successes"][metric]) / len(all_results)
            for metric in metric_names
        }

        for metric in metric_names:
            print(f"  {metric}: avg={avg_scores[metric]:.2f}, pass_rate={pass_rates[metric]*100:.0f}%")

        # Assert minimum pass rate for faithfulness (most critical metric)
        assert pass_rates["Faithfulness"] >= 0.5, f"Faithfulness pass rate too low: {pass_rates['Faithfulness']*100:.0f}%"


# ===================== Edge Case Tests =====================
# Note: These tests require DeepEval's structured output feature which doesn't work
# reliably through Alita's LiteLLM proxy. Skip them when running against Alita.

@pytest.mark.rag_eval
@pytest.mark.skip(reason="Edge case tests require structured output which is not supported by Alita's LiteLLM proxy")
class TestRAGEdgeCases:
    """Test RAG behavior with edge cases and boundary conditions.

    Note: These tests are skipped by default because DeepEval metrics use
    structured output (schema parameter) which doesn't work reliably through
    Alita's LiteLLM proxy. Run with direct OpenAI API for these tests.
    """

    def test_short_query(self, indexer_toolkit, deepeval_model):
        """Test handling of minimal/short queries."""
        query = "subagent"  # Very short query
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        metric = FaithfulnessMetric(threshold=THRESHOLD_EDGE_CASE, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nEdge Case - Short Query:")
        print(f"  Query: '{query}'")
        print(f"  Score: {metric.score} (threshold: {THRESHOLD_EDGE_CASE})")

        # Should still return some results
        assert len(retrieval_context) > 0, "Should retrieve some context even for short queries"
        # Metric should run successfully (score exists)
        assert metric.score is not None, "Metric should produce a score"

    def test_out_of_domain_query(self, indexer_toolkit, deepeval_model):
        """Test handling of queries outside the indexed domain."""
        query = "How do I cook pasta?"  # Completely unrelated to Claude/AI
        actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        metric = ContextualRelevancyMetric(threshold=THRESHOLD_EDGE_CASE, model=deepeval_model, async_mode=False)
        metric.measure(test_case)

        print(f"\nEdge Case - Out of Domain Query:")
        print(f"  Query: '{query}'")
        print(f"  Relevancy Score: {metric.score} (threshold: {THRESHOLD_EDGE_CASE})")

        # Relevancy should be low for out-of-domain queries
        # This validates that the metric correctly identifies irrelevant results
        assert metric.score is not None, "Metric should produce a score"
        # Out-of-domain queries should have low relevancy (below normal threshold)
        assert metric.score < THRESHOLD_CONTEXTUAL_RELEVANCY, f"Out-of-domain query should have low relevancy, got {metric.score}"

    def test_specific_vs_general_query(self, indexer_toolkit, deepeval_model):
        """Compare retrieval quality between specific and general queries."""
        queries = [
            ("allowedTools Task coordinator", "specific"),
            ("how to build agents with Claude", "general"),
        ]

        print(f"\nEdge Case - Specific vs General Queries:")

        for query, query_type in queries:
            actual_output, retrieval_context = search_and_extract_context(indexer_toolkit, query)

            test_case = LLMTestCase(
                input=query,
                actual_output=actual_output,
                retrieval_context=retrieval_context,
            )

            metric = ContextualRelevancyMetric(threshold=THRESHOLD_EDGE_CASE, model=deepeval_model, async_mode=False)
            metric.measure(test_case)

            status = "PASS" if metric.score >= THRESHOLD_CONTEXTUAL_RELEVANCY else "LOW"
            print(f"  [{query_type.upper()}] '{query}': {metric.score:.2f} [{status}]")
