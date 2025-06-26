import pytest
from unittest.mock import Mock, patch, MagicMock
import tiktoken
from typing import List, Dict, Any

from alita_sdk.runtime.llms.preloaded import PreloadedChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestPreloadedChatModel:
    """Test suite for PreloadedChatModel functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.model = PreloadedChatModel.model_construct(
            token_limit=100,
            max_tokens=50,
            model_name="test-model"
        )
    
    def test_count_tokens_string(self):
        """Test token counting for string input"""
        text = "Hello world"
        count = PreloadedChatModel._count_tokens(text)
        assert isinstance(count, int)
        assert count > 0
    
    def test_count_tokens_message_list(self):
        """Test token counting for list of messages"""
        messages = [
            {"content": "Hello"},
            {"content": "world"},
            {"content": "test"}
        ]
        count = PreloadedChatModel._count_tokens(messages)
        assert isinstance(count, int)
        assert count > 0
    
    def test_count_tokens_empty_string(self):
        """Test token counting for empty string"""
        count = PreloadedChatModel._count_tokens("")
        assert count == 0
    
    def test_count_tokens_empty_list(self):
        """Test token counting for empty message list"""
        count = PreloadedChatModel._count_tokens([])
        assert count == 0
    
    def test_count_tokens_message_with_empty_content(self):
        """Test token counting for messages with empty content"""
        messages = [
            {"content": ""},
            {"content": "hello"},
            {"content": ""}
        ]
        count = PreloadedChatModel._count_tokens(messages)
        # Should only count tokens from "hello"
        hello_count = PreloadedChatModel._count_tokens("hello")
        assert count == hello_count
    
    def test_count_tokens_consistency(self):
        """Test that token counting is consistent"""
        text = "This is a test message"
        count1 = PreloadedChatModel._count_tokens(text)
        count2 = PreloadedChatModel._count_tokens(text)
        assert count1 == count2
    
    def test_count_tokens_additive(self):
        """Test that token counting is additive for message lists"""
        text1 = "Hello"
        text2 = "world"
        messages = [{"content": text1}, {"content": text2}]
        
        individual_count = (
            PreloadedChatModel._count_tokens(text1) + 
            PreloadedChatModel._count_tokens(text2)
        )
        combined_count = PreloadedChatModel._count_tokens(messages)
        
        assert combined_count == individual_count
    
    def test_remove_non_system_messages_no_removal(self):
        """Test removing messages when no removal needed"""
        messages = [
            {"role": "system", "content": "system message"},
            {"role": "human", "content": "user message"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 0)
        
        assert result == messages
        assert removed_count == 0
    
    def test_remove_non_system_messages_remove_some(self):
        """Test removing some non-system messages"""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "human", "content": "human1"},
            {"role": "ai", "content": "ai1"},
            {"role": "human", "content": "human2"},
            {"role": "ai", "content": "ai2"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 2)
        
        expected = [
            {"role": "system", "content": "system"},
            {"role": "human", "content": "human2"},
            {"role": "ai", "content": "ai2"}
        ]
        
        assert result == expected
        assert removed_count == 2
    
    def test_remove_non_system_messages_remove_all_non_system(self):
        """Test removing all non-system messages"""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "human", "content": "human1"},
            {"role": "ai", "content": "ai1"},
            {"role": "human", "content": "human2"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 3)
        
        expected = [{"role": "system", "content": "system"}]
        
        assert result == expected
        assert removed_count == 3
    
    def test_remove_non_system_messages_only_system(self):
        """Test with only system messages"""
        messages = [
            {"role": "system", "content": "system1"},
            {"role": "system", "content": "system2"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 1)
        
        assert result == messages
        assert removed_count == 0
    
    def test_remove_non_system_messages_no_system(self):
        """Test with no system messages"""
        messages = [
            {"role": "human", "content": "human1"},
            {"role": "ai", "content": "ai1"},
            {"role": "human", "content": "human2"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 1)
        
        expected = [
            {"role": "ai", "content": "ai1"},
            {"role": "human", "content": "human2"}
        ]
        
        assert result == expected
        assert removed_count == 1
    
    def test_remove_non_system_messages_empty_list(self):
        """Test with empty message list"""
        result, removed_count = PreloadedChatModel._remove_non_system_messages([], 1)
        
        assert result == []
        assert removed_count == 0
    
    def test_remove_non_system_messages_remove_more_than_available(self):
        """Test removing more messages than available"""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "human", "content": "human1"}
        ]
        
        result, removed_count = PreloadedChatModel._remove_non_system_messages(messages, 5)
        
        expected = [{"role": "system", "content": "system"}]
        
        assert result == expected
        assert removed_count == 1
    
    def test_limit_tokens_no_limit_needed(self):
        """Test token limiting when no limiting is needed"""
        model = PreloadedChatModel.model_construct(token_limit=1000, max_tokens=100)
        
        messages = [
            {"role": "system", "content": "short"},
            {"role": "human", "content": "message"}
        ]
        
        result = model._limit_tokens(messages)
        assert result == messages
    
    def test_limit_tokens_with_limiting(self):
        """Test token limiting when limiting is needed"""
        # Use very small token limit to force limiting
        model = PreloadedChatModel.model_construct(token_limit=10, max_tokens=5)
        
        messages = [
            {"role": "system", "content": "system message"},
            {"role": "human", "content": "first human message"},
            {"role": "ai", "content": "first ai response"},
            {"role": "human", "content": "second human message"},
            {"role": "ai", "content": "second ai response"}
        ]
        
        result = model._limit_tokens(messages)
        
        # Should preserve system messages and remove some messages
        assert len(result) <= len(messages)
        assert any(msg["role"] == "system" for msg in result)
        
        # Should have removed some messages to fit token limit
        token_count = model._count_tokens(result)
        assert token_count + 5 <= 10  # Should fit within token limit
    
    def test_limit_tokens_only_system_messages(self):
        """Test token limiting with only system messages"""
        model = PreloadedChatModel.model_construct(token_limit=50, max_tokens=25)
        
        messages = [
            {"role": "system", "content": "system1"},
            {"role": "system", "content": "system2"}
        ]
        
        result = model._limit_tokens(messages)
        # System messages should be preserved
        assert result == messages
    
    def test_limit_tokens_empty_messages(self):
        """Test token limiting with empty message list"""
        model = PreloadedChatModel.model_construct(token_limit=100, max_tokens=50)
        
        result = model._limit_tokens([])
        assert result == []
    
    def test_limit_tokens_very_long_messages(self):
        """Test token limiting with very long messages"""
        model = PreloadedChatModel.model_construct(token_limit=20, max_tokens=10)
        
        long_content = "This is a very long message " * 20
        messages = [
            {"role": "system", "content": "system"},
            {"role": "human", "content": long_content},
            {"role": "ai", "content": long_content}
        ]
        
        result = model._limit_tokens(messages)
        
        # Should still preserve system message
        assert any(msg["role"] == "system" for msg in result)
        # Should have fewer messages than original
        assert len(result) <= len(messages)
    
    def test_limit_tokens_progressive_removal(self):
        """Test that token limiting removes messages progressively"""
        model = PreloadedChatModel.model_construct(token_limit=30, max_tokens=15)
        
        messages = [
            {"role": "system", "content": "s"},
            {"role": "human", "content": "h1"},
            {"role": "ai", "content": "a1"},
            {"role": "human", "content": "h2"},
            {"role": "ai", "content": "a2"},
            {"role": "human", "content": "h3"},
            {"role": "ai", "content": "a3"}
        ]
        
        result = model._limit_tokens(messages)
        
        # Should preserve system message
        system_msgs = [msg for msg in result if msg["role"] == "system"]
        assert len(system_msgs) == 1
        
        # Should preserve most recent messages
        if len(result) > 1:
            assert result[-1] == messages[-1]
    
    def test_count_tokens_with_different_encodings(self):
        """Test token counting with different text types"""
        # Test with various text types
        test_cases = [
            "Simple text",
            "Text with números and símbolos!",
            "Unicode: 🚀 🌟 ⭐",
            "Very long text " * 50,
            "JSON: {\"key\": \"value\", \"number\": 123}",
            "Code: def hello(): return 'world'"
        ]
        
        for text in test_cases:
            count = PreloadedChatModel._count_tokens(text)
            assert isinstance(count, int)
            assert count >= 0
    
    def test_mixed_message_roles(self):
        """Test with various message roles"""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user message"},
            {"role": "assistant", "content": "assistant response"},
            {"role": "function", "content": "function result"},
            {"role": "tool", "content": "tool output"}
        ]
        
        # Test token counting works with all role types
        count = PreloadedChatModel._count_tokens(messages)
        assert isinstance(count, int)
        assert count > 0
        
        # Test removal works with different roles
        result, removed = PreloadedChatModel._remove_non_system_messages(messages, 2)
        assert len(result) < len(messages)
        assert removed > 0
