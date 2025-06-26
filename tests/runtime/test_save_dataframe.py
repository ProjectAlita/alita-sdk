import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
from io import StringIO
import tempfile
import os

from alita_sdk.runtime.utils.save_dataframe import save_dataframe_to_artifact
from langchain_core.tools import ToolException


class TestSaveDataframe:
    """Test suite for save_dataframe_to_artifact function"""
    
    def test_save_dataframe_success_default_options(self):
        """Test successful save with default CSV options"""
        df = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'test.csv')
        
        mock_wrapper.create_file.assert_called_once()
        args, _ = mock_wrapper.create_file.call_args
        assert args[0] == 'test.csv'
        assert result is None  # No exception returned
    
    def test_save_dataframe_success_custom_options(self):
        """Test successful save with custom CSV options"""
        df = pd.DataFrame({'a': [1, 2], 'b': ['x', 'y']})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        csv_options = {'sep': ';', 'index': False}
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'test.csv', csv_options)
        
        mock_wrapper.create_file.assert_called_once()
        assert result is None
    
    def test_save_dataframe_empty_dataframe(self):
        """Test with empty DataFrame"""
        df = pd.DataFrame()
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'empty.csv')
        
        mock_wrapper.create_file.assert_called_once()
        assert result is None
    
    def test_save_dataframe_wrapper_exception(self):
        """Test when wrapper.create_file raises exception"""
        df = pd.DataFrame({'a': [1]})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        mock_wrapper.create_file.side_effect = RuntimeError('Storage error')
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'test.csv')
        
        assert isinstance(result, ToolException)
        assert 'Failed to save DataFrame to artifact repository' in str(result)
        assert 'Storage error' in str(result)
    
    def test_save_dataframe_csv_conversion_error(self):
        """Test when DataFrame.to_csv raises exception"""
        # Create a DataFrame with problematic data that might cause CSV conversion issues
        df = pd.DataFrame({'a': [1, 2, 3]})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        # Mock the to_csv method to raise an exception
        with patch.object(pd.DataFrame, 'to_csv', side_effect=ValueError('CSV conversion error')):
            result = save_dataframe_to_artifact(mock_wrapper, df, 'test.csv')
        
        assert isinstance(result, ToolException)
        assert 'Failed to save DataFrame to artifact repository' in str(result)
    
    def test_save_dataframe_none_csv_options(self):
        """Test with None csv_options"""
        df = pd.DataFrame({'a': [1]})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'test.csv', None)
        
        mock_wrapper.create_file.assert_called_once()
        assert result is None
    
    def test_save_dataframe_complex_data(self):
        """Test with complex DataFrame data types"""
        df = pd.DataFrame({
            'int_col': [1, 2, 3],
            'float_col': [1.1, 2.2, 3.3],
            'str_col': ['a', 'b', 'c'],
            'bool_col': [True, False, True],
            'date_col': pd.date_range('2023-01-01', periods=3)
        })
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'complex.csv')
        
        mock_wrapper.create_file.assert_called_once()
        args, _ = mock_wrapper.create_file.call_args
        csv_content = args[1]
        assert isinstance(csv_content, str)
        assert result is None
    
    def test_save_dataframe_special_characters_filename(self):
        """Test with special characters in filename"""
        df = pd.DataFrame({'a': [1]})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'file with spaces & symbols.csv')
        
        mock_wrapper.create_file.assert_called_once()
        args, _ = mock_wrapper.create_file.call_args
        assert args[0] == 'file with spaces & symbols.csv'
        assert result is None
    
    def test_save_dataframe_large_dataset(self):
        """Test with larger DataFrame"""
        # Create a larger DataFrame
        df = pd.DataFrame({
            'col1': range(1000),
            'col2': [f'value_{i}' for i in range(1000)],
            'col3': [i * 0.1 for i in range(1000)]
        })
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        result = save_dataframe_to_artifact(mock_wrapper, df, 'large.csv')
        
        mock_wrapper.create_file.assert_called_once()
        assert result is None
    
    def test_save_dataframe_csv_options_validation(self):
        """Test various CSV options are properly passed through"""
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        mock_wrapper = Mock()
        mock_wrapper.bucket = 'test-bucket'
        
        csv_options = {
            'index': False,
            'header': True,
            'sep': '\t',
            'quoting': 1,
            'encoding': 'utf-8'
        }
        
        # Mock to_csv to capture the options passed
        with patch.object(pd.DataFrame, 'to_csv') as mock_to_csv:
            save_dataframe_to_artifact(mock_wrapper, df, 'test.csv', csv_options)
            
            # Verify to_csv was called with the right options
            mock_to_csv.assert_called_once()
            call_args = mock_to_csv.call_args
            for key, value in csv_options.items():
                assert call_args[1][key] == value
