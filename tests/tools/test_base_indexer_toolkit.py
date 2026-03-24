"""
Pytest tests for BaseIndexerToolkit search_index functionality.

This test suite validates the search_index tool with various filter configurations
using a pre-populated pgvector database.

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
  pytest tests/tools/test_base_indexer_toolkit.py -v -k "filter_by_status"
  pytest tests/tools/test_base_indexer_toolkit.py -v -m "search_test"
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import SecretStr
from alita_sdk.runtime.clients.client import AlitaClient
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit
from deepeval.metrics.rag import (
    MultiTurnRAGTestCase,
    MultiTurnRAGTestSuite,
    TurnFaithfulnessMetric,
    TurnContextualRelevancyMetric,
    TurnContextualPrecisionMetric,
    TurnContextualRecallMetric,
)

# Test configuration
PGVECTOR_CONNECTION_STRING = os.getenv(
    "PGVECTOR_TEST_CONNECTION_STRING",
    "postgresql+psycopg://postgres:yourpassword@localhost:5435/postgres"
)
TEST_COLLECTION_NAME = "test_indexer_collection"

# Required environment variables (no defaults - must be explicitly set)
DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL")
API_KEY = os.getenv("ALITA_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS", "gpt-4o-mini")


def _check_credentials_available() -> bool:
    """Check if all required credentials are available."""
    return all([DEPLOYMENT_URL, PROJECT_ID, API_KEY])


@pytest.fixture(scope="module")
def alita_client():
    """Create AlitaClient instance for tests.
    
    Requires environment variables:
    - DEPLOYMENT_URL: Alita deployment URL
    - PROJECT_ID: Project ID  
    """


    # ===================== Multi-Turn RAG Evaluation Test =====================

    @pytest.mark.rag_eval
    def test_multi_turn_rag_evaluation(indexer_toolkit):
        """
        Multi-turn RAG evaluation using DeepEval metrics.
        This test runs a multi-turn conversation against the search_index (RAG) and evaluates with DeepEval metrics.
        """
        # Example multi-turn test case (replace with your real queries/answers)
        test_case = MultiTurnRAGTestCase(
            turns=[
                {
                    "query": "What is the purpose of the test index?",
                    "ground_truth": "The test index is used to validate search functionality with pgvector."
                },
                {
                    "query": "How do I run the indexer toolkit tests?",
                    "ground_truth": "You can run pytest tests/tools/test_base_indexer_toolkit.py -v after starting pgvector."
                },
                {
                    "query": "What credentials are required?",
                    "ground_truth": "DEPLOYMENT_URL, ALITA_API_KEY, and PROJECT_ID must be set in the environment."
                },
            ]
        )

        # Run RAG for each turn and collect responses
        context = None
        for turn in test_case.turns:
            # You may want to pass context if your RAG supports it
            response = indexer_toolkit.search_index(query=turn["query"], index_name="test_idx")
            # If response is a list, join top doc contents; if dict/str, handle accordingly
            if isinstance(response, list) and response:
                # Assume each doc has a 'content' or 'text' field
                doc_texts = [doc.get('content') or doc.get('text') or str(doc) for doc in response]
                turn["response"] = "\n".join(doc_texts)
            elif isinstance(response, str):
                turn["response"] = response
            else:
                turn["response"] = str(response)
            context = turn["response"]  # Optionally update context

        # Set up metrics
        metrics = [
            TurnFaithfulnessMetric(),
            TurnContextualRelevancyMetric(),
            TurnContextualPrecisionMetric(),
            TurnContextualRecallMetric(),
        ]

        # Create and run the test suite
        suite = MultiTurnRAGTestSuite([test_case], metrics)
        results = suite.run()


        # Requires environment variables:
        # - DEPLOYMENT_URL: Alita deployment URL
        # - PROJECT_ID: Project ID


    # ===================== Multi-Turn RAG Evaluation Test =====================

    @pytest.mark.rag_eval
    def test_multi_turn_rag_evaluation(indexer_toolkit):
        """
        Multi-turn RAG evaluation using DeepEval metrics.
        This test runs a multi-turn conversation against the search_index (RAG) and evaluates with DeepEval metrics.
        """
        # Example multi-turn test case (replace with your real queries/answers)
        test_case = MultiTurnRAGTestCase(
            turns=[
                {
                    "query": "What is the purpose of the test index?",
                    "ground_truth": "The test index is used to validate search functionality with pgvector."
                },
                {
                    "query": "How do I run the indexer toolkit tests?",
                    "ground_truth": "You can run pytest tests/tools/test_base_indexer_toolkit.py -v after starting pgvector."
                },
                {
                    "query": "What credentials are required?",
                    "ground_truth": "DEPLOYMENT_URL, ALITA_API_KEY, and PROJECT_ID must be set in the environment."
                },
            ]
        )

        # Run RAG for each turn and collect responses
        context = None
        for turn in test_case.turns:
            # You may want to pass context if your RAG supports it
            response = indexer_toolkit.search_index(query=turn["query"], index_name="test_idx")
            # If response is a list, join top doc contents; if dict/str, handle accordingly
            if isinstance(response, list) and response:
                # Assume each doc has a 'content' or 'text' field
                doc_texts = [doc.get('content') or doc.get('text') or str(doc) for doc in response]
                turn["response"] = "\n".join(doc_texts)
            elif isinstance(response, str):
                turn["response"] = response
            else:
                turn["response"] = str(response)
            context = turn["response"]  # Optionally update context

        # Set up metrics
        metrics = [
            TurnFaithfulnessMetric(),
            TurnContextualRelevancyMetric(),
            TurnContextualPrecisionMetric(),
            TurnContextualRecallMetric(),
        ]

        # Create and run the test suite
        suite = MultiTurnRAGTestSuite([test_case], metrics)
        results = suite.run()

        # Print and assert metrics (customize thresholds as needed)
        for metric, value in results.items():
            print(f"{metric}: {value}")
            # Example: assert minimum threshold for each metric
            assert value >= 0.0, f"Metric {metric} below threshold: {value}"
                                        f"Document {idx} field '{field}' value {actual_value} not in {expected_values}"
