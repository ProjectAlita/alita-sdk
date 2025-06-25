import pytest
import re
from unittest.mock import Mock, patch

from alita_sdk.runtime.utils.utils import clean_string, TOOLKIT_SPLITTER, clean_string_pattern


class TestUtilsModule:
    """Test suite for runtime utils module"""
    
    def test_toolkit_splitter_constant(self):
        """Test TOOLKIT_SPLITTER constant"""
        assert TOOLKIT_SPLITTER == "___"
        assert isinstance(TOOLKIT_SPLITTER, str)
        assert len(TOOLKIT_SPLITTER) == 3
    
    def test_clean_string_pattern_regex(self):
        """Test clean_string_pattern compiled regex"""
        assert isinstance(clean_string_pattern, type(re.compile('')))
        
        # Test the pattern matches expected characters
        test_string = "abc123_.-XYZ!@#$%^&*()"
        matches = clean_string_pattern.findall(test_string)
        
        # Should match all characters except alphanumeric, underscore, period, and hyphen
        expected_matches = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')']
        assert matches == expected_matches
    
    def test_clean_string_basic(self):
        """Test basic clean_string functionality"""
        # Test with special characters
        result = clean_string('hello world!')
        assert result == 'helloworld'
        
        # Test with allowed characters
        result = clean_string('a_b-c.d')
        assert result == 'a_b-c.d'
        
        # Test with mixed content
        result = clean_string('test123_file-name.txt')
        assert result == 'test123_file-name.txt'
    
    def test_clean_string_empty_input(self):
        """Test clean_string with empty input"""
        result = clean_string('')
        assert result == ''
    
    def test_clean_string_only_special_chars(self):
        """Test clean_string with only special characters"""
        result = clean_string('!@#$%^&*()')
        assert result == ''
    
    def test_clean_string_only_allowed_chars(self):
        """Test clean_string with only allowed characters"""
        test_input = 'abcABC123_.-'
        result = clean_string(test_input)
        assert result == test_input
    
    def test_clean_string_whitespace(self):
        """Test clean_string with various whitespace characters"""
        # Spaces should be removed
        result = clean_string('hello world')
        assert result == 'helloworld'
        
        # Tabs should be removed
        result = clean_string('hello\tworld')
        assert result == 'helloworld'
        
        # Newlines should be removed
        result = clean_string('hello\nworld')
        assert result == 'helloworld'
        
        # Carriage returns should be removed
        result = clean_string('hello\rworld')
        assert result == 'helloworld'
    
    def test_clean_string_unicode_characters(self):
        """Test clean_string with Unicode characters"""
        # Unicode characters should be removed
        result = clean_string('hello🌟world')
        assert result == 'helloworld'
        
        # Accented characters should be removed
        result = clean_string('café')
        assert result == 'caf'
        
        # Mix of unicode and allowed chars
        result = clean_string('test_file-中文.txt')
        assert result == 'test_file-.txt'
    
    def test_clean_string_numbers_and_letters(self):
        """Test clean_string preserves numbers and letters"""
        result = clean_string('abc123XYZ789')
        assert result == 'abc123XYZ789'
    
    def test_clean_string_special_allowed_chars(self):
        """Test clean_string preserves underscore, period, and hyphen"""
        result = clean_string('test_file-name.extension')
        assert result == 'test_file-name.extension'
    
    def test_clean_string_mixed_complex(self):
        """Test clean_string with complex mixed input"""
        test_input = 'My_File-Name.txt (copy) [2023]'
        expected = 'My_File-Name.txtcopy2023'
        result = clean_string(test_input)
        assert result == expected
    
    def test_clean_string_brackets_and_parentheses(self):
        """Test clean_string removes brackets and parentheses"""
        result = clean_string('file[1].txt')
        assert result == 'file1.txt'
        
        result = clean_string('file(copy).txt')
        assert result == 'filecopy.txt'
        
        result = clean_string('file{backup}.txt')
        assert result == 'filebackup.txt'
    
    def test_clean_string_common_symbols(self):
        """Test clean_string removes common symbols"""
        symbols = '!@#$%^&*()+=[]{}|\\:";\'<>?/,`~'
        result = clean_string(f'test{symbols}file')
        assert result == 'testfile'
    
    def test_clean_string_preserves_case(self):
        """Test clean_string preserves case of letters"""
        result = clean_string('MyFile_NAME.TXT')
        assert result == 'MyFile_NAME.TXT'
    
    def test_clean_string_long_string(self):
        """Test clean_string with long string"""
        long_input = 'a' * 1000 + '!' * 500 + 'b' * 1000
        result = clean_string(long_input)
        expected = 'a' * 1000 + 'b' * 1000
        assert result == expected
        assert len(result) == 2000
    
    def test_clean_string_regex_pattern_directly(self):
        """Test the clean_string_pattern regex directly"""
        # Test that it matches what we expect
        test_cases = [
            ('abc', []),  # No matches for allowed chars
            ('123', []),  # No matches for numbers
            ('_.-', []),  # No matches for allowed symbols
            ('!@#', ['!', '@', '#']),  # Matches for disallowed symbols
            ('hello world!', [' ', '!']),  # Matches spaces and symbols
        ]
        
        for test_input, expected_matches in test_cases:
            matches = clean_string_pattern.findall(test_input)
            assert matches == expected_matches, f"Failed for input: {test_input}"
    
    def test_clean_string_pattern_substitute(self):
        """Test using the pattern for substitution directly"""
        test_input = "test!@#file"
        result = re.sub(clean_string_pattern, '', test_input)
        assert result == "testfile"
        
        # This should be equivalent to clean_string
        clean_result = clean_string(test_input)
        assert result == clean_result
    
    def test_clean_string_idempotent(self):
        """Test that clean_string is idempotent"""
        test_input = "test!@#file_name-123.txt"
        first_clean = clean_string(test_input)
        second_clean = clean_string(first_clean)
        
        assert first_clean == second_clean
        # Second application should not change anything
        assert second_clean == "testfile_name-123.txt"
    
    def test_clean_string_type_validation(self):
        """Test clean_string input type handling"""
        # Should work with string input
        result = clean_string("test")
        assert isinstance(result, str)
        
        # Test with non-string input (should raise TypeError)
        with pytest.raises(TypeError):
            clean_string(123)
    
    def test_clean_string_none_input(self):
        """Test clean_string with None input"""
        with pytest.raises(TypeError):
            clean_string(None)
    
    def test_regex_pattern_compilation(self):
        """Test that the regex pattern is properly compiled"""
        # Test that pattern is compiled and works
        assert hasattr(clean_string_pattern, 'findall')
        assert hasattr(clean_string_pattern, 'sub')
        assert hasattr(clean_string_pattern, 'match')
        
        # Test pattern string
        expected_pattern = r'[^a-zA-Z0-9_.-]'
        # We can't directly access the pattern string from compiled regex in all Python versions
        # But we can test its behavior
        test_str = "abc123_.-XYZ!@#"
        matches = clean_string_pattern.findall(test_str)
        assert matches == ['!', '@', '#']
