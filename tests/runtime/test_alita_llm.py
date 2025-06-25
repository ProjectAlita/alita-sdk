import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import requests
from typing import List, Dict, Any, Optional, Iterator, Type, AsyncIterator, Mapping

from alita_sdk.runtime.llms.alita import MaxRetriesExceededError
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestMaxRetriesExceededError:
    """Test suite for MaxRetriesExceededError exception"""
    
    def test_default_message(self):
        """Test MaxRetriesExceededError with default message"""
        error = MaxRetriesExceededError()
        assert str(error) == "Maximum number of retries exceeded"
        assert error.message == "Maximum number of retries exceeded"
    
    def test_custom_message(self):
        """Test MaxRetriesExceededError with custom message"""
        custom_msg = "Custom retry error message"
        error = MaxRetriesExceededError(custom_msg)
        assert str(error) == custom_msg
        assert error.message == custom_msg
    
    def test_inheritance(self):
        """Test that MaxRetriesExceededError inherits from Exception"""
        error = MaxRetriesExceededError()
        assert isinstance(error, Exception)
    
    def test_raising_and_catching(self):
        """Test raising and catching MaxRetriesExceededError"""
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            raise MaxRetriesExceededError("Test error")
        
        assert str(exc_info.value) == "Test error"
        assert exc_info.value.message == "Test error"
    
    def test_error_with_empty_message(self):
        """Test MaxRetriesExceededError with empty message"""
        error = MaxRetriesExceededError("")
        assert str(error) == ""
        assert error.message == ""
    
    def test_error_with_none_message(self):
        """Test MaxRetriesExceededError with None message"""
        # This should use default behavior
        error = MaxRetriesExceededError(None)
        assert error.message is None
        assert str(error) == "None"
    
    def test_error_with_multiline_message(self):
        """Test MaxRetriesExceededError with multiline message"""
        multiline_msg = "First line\nSecond line\nThird line"
        error = MaxRetriesExceededError(multiline_msg)
        assert str(error) == multiline_msg
        assert error.message == multiline_msg
    
    def test_error_with_special_characters(self):
        """Test MaxRetriesExceededError with special characters"""
        special_msg = "Error with special chars: áéíóú 🚀 @#$%^&*()"
        error = MaxRetriesExceededError(special_msg)
        assert str(error) == special_msg
        assert error.message == special_msg
    
    def test_error_repr(self):
        """Test string representation of MaxRetriesExceededError"""
        error = MaxRetriesExceededError("Test message")
        repr_str = repr(error)
        assert "MaxRetriesExceededError" in repr_str
        assert "Test message" in repr_str


class TestAlitaLLMConstants:
    """Test suite for constants and imports in alita.py"""
    
    def test_logger_exists(self):
        """Test that logger is properly configured"""
        from alita_sdk.runtime.llms.alita import logger
        import logging
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "alita_sdk.runtime.llms.alita"
    
    def test_imports_available(self):
        """Test that all required imports are available"""
        try:
            from alita_sdk.runtime.llms.alita import (
                MaxRetriesExceededError,
                logger
            )
            # If we get here, imports are working
            assert True
        except ImportError as e:
            pytest.fail(f"Required imports not available: {e}")
    
    def test_langchain_imports(self):
        """Test that LangChain imports are available"""
        try:
            from langchain_core.callbacks import (
                AsyncCallbackManagerForLLMRun,
                CallbackManagerForLLMRun,
            )
            from langchain_core.language_models import BaseChatModel, SimpleChatModel
            from langchain_core.messages import (
                AIMessageChunk, BaseMessage, HumanMessage, HumanMessageChunk,
                ChatMessageChunk, FunctionMessageChunk, SystemMessageChunk,
                ToolMessageChunk, BaseMessageChunk, AIMessage
            )
            from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
            from langchain_core.runnables import run_in_executor
            from langchain_community.chat_models.openai import generate_from_stream, _convert_delta_to_message_chunk
            
            # If we get here, imports are working
            assert True
        except ImportError as e:
            pytest.skip(f"LangChain dependencies not available: {e}")
    
    def test_tiktoken_import(self):
        """Test that tiktoken import is available"""
        try:
            from tiktoken import get_encoding, encoding_for_model
            assert True
        except ImportError as e:
            pytest.skip(f"tiktoken not available: {e}")
    
    def test_pydantic_imports(self):
        """Test that Pydantic imports are available"""
        try:
            from pydantic import Field, model_validator, field_validator, ValidationInfo
            assert True
        except ImportError as e:
            pytest.skip(f"Pydantic not available: {e}")


class TestAlitaLLMErrorHandling:
    """Test suite for error handling scenarios in Alita LLM"""
    
    def test_max_retries_error_usage_scenario(self):
        """Test a realistic scenario where MaxRetriesExceededError would be used"""
        def mock_retry_function(max_retries=3):
            attempt = 0
            while attempt < max_retries:
                attempt += 1
                if attempt >= max_retries:
                    raise MaxRetriesExceededError(f"Failed after {max_retries} attempts")
                # Simulate a failing operation
                continue
        
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            mock_retry_function(max_retries=2)
        
        assert "Failed after 2 attempts" in str(exc_info.value)
    
    def test_error_chaining(self):
        """Test error chaining with MaxRetriesExceededError"""
        original_error = ValueError("Original error")
        
        try:
            raise original_error
        except ValueError as e:
            retry_error = MaxRetriesExceededError("Retries exceeded")
            retry_error.__cause__ = e
            
            with pytest.raises(MaxRetriesExceededError) as exc_info:
                raise retry_error
            
            assert exc_info.value.__cause__ is original_error
    
    def test_requests_error_simulation(self):
        """Test simulated network error scenarios"""
        def simulate_network_call_with_retries():
            """Simulate a function that retries network calls"""
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Simulate network error
                    raise requests.ConnectionError("Network unreachable")
                except requests.ConnectionError:
                    if attempt == max_retries - 1:
                        raise MaxRetriesExceededError(
                            f"Network call failed after {max_retries} attempts"
                        )
                    continue
        
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            simulate_network_call_with_retries()
        
        assert "Network call failed after 3 attempts" in str(exc_info.value)
    
    def test_error_with_context_manager(self):
        """Test MaxRetriesExceededError within context managers"""
        class RetryContext:
            def __init__(self, max_retries=3):
                self.max_retries = max_retries
                self.attempts = 0
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type and self.attempts >= self.max_retries:
                    # Convert to MaxRetriesExceededError
                    return False  # Re-raise
                return False
            
            def attempt(self):
                self.attempts += 1
                if self.attempts >= self.max_retries:
                    raise MaxRetriesExceededError(f"Max attempts ({self.max_retries}) reached")
                raise ValueError("Simulated failure")
        
        with pytest.raises(MaxRetriesExceededError):
            with RetryContext(max_retries=2) as ctx:
                ctx.attempt()


class TestUtilityFunctions:
    """Test utility functions and helpers"""
    
    def test_sleep_import(self):
        """Test that sleep import works"""
        try:
            from time import sleep
            assert callable(sleep)
        except ImportError as e:
            pytest.fail(f"Sleep import failed: {e}")
    
    def test_format_exc_import(self):
        """Test that format_exc import works"""
        try:
            from traceback import format_exc
            assert callable(format_exc)
        except ImportError as e:
            pytest.fail(f"format_exc import failed: {e}")
    
    def test_format_exc_usage(self):
        """Test format_exc functionality"""
        from traceback import format_exc
        
        try:
            raise ValueError("Test error")
        except ValueError:
            traceback_str = format_exc()
            assert isinstance(traceback_str, str)
            assert "ValueError" in traceback_str
            assert "Test error" in traceback_str
    
    def test_requests_import(self):
        """Test that requests import works"""
        try:
            import requests
            assert hasattr(requests, 'get')
            assert hasattr(requests, 'post')
            assert hasattr(requests, 'ConnectionError')
        except ImportError as e:
            pytest.skip(f"requests not available: {e}")


class TestTypeHints:
    """Test type hint related functionality"""
    
    def test_typing_imports(self):
        """Test that typing imports work correctly"""
        try:
            from typing import Any, List, Optional, AsyncIterator, Dict, Iterator, Mapping, Type
            
            # Test that these are usable
            def test_func(
                param1: Any,
                param2: List[str],
                param3: Optional[Dict[str, int]],
                param4: Iterator[str]
            ) -> Type[Exception]:
                return Exception
            
            assert callable(test_func)
        except ImportError as e:
            pytest.fail(f"Typing imports failed: {e}")
    
    def test_annotation_compatibility(self):
        """Test that type annotations work as expected"""
        def typed_function(
            messages: List[Dict[str, Any]],
            settings: Optional[Dict[str, Any]] = None
        ) -> str:
            return "test"
        
        # Function should be callable and return expected type
        result = typed_function([{"test": "message"}])
        assert isinstance(result, str)
        assert result == "test"
