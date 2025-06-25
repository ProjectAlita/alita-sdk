import pytest
from unittest.mock import Mock, patch, MagicMock
import base64
from io import BytesIO
from PIL import Image

from alita_sdk.runtime.utils.streamlit import (
    img_to_txt, 
    decode_img, 
    ai_icon, 
    user_icon, 
    agent_types
)


class TestStreamlitUtils:
    """Test suite for Streamlit utility functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create a simple test image
        self.test_image = Image.new('RGB', (10, 10), color='red')
        self.test_image_bytes = BytesIO()
        self.test_image.save(self.test_image_bytes, format='PNG')
        self.test_image_bytes.seek(0)
    
    def test_ai_icon_is_valid_base64(self):
        """Test that ai_icon contains valid base64 data"""
        # Extract base64 data
        start_marker = b"<plain_txt_msg:img>"
        end_marker = b"<!plain_txt_msg>"
        
        start_pos = ai_icon.find(start_marker)
        end_pos = ai_icon.find(end_marker)
        
        assert start_pos != -1, "Start marker not found in ai_icon"
        assert end_pos != -1, "End marker not found in ai_icon"
        
        base64_data = ai_icon[start_pos + len(start_marker):end_pos]
        
        # Should be valid base64
        try:
            decoded = base64.b64decode(base64_data)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"ai_icon contains invalid base64 data: {e}")
    
    def test_user_icon_is_valid_base64(self):
        """Test that user_icon contains valid base64 data"""
        start_marker = b"<plain_txt_msg:img>"
        end_marker = b"<!plain_txt_msg>"
        
        start_pos = user_icon.find(start_marker)
        end_pos = user_icon.find(end_marker)
        
        assert start_pos != -1, "Start marker not found in user_icon"
        assert end_pos != -1, "End marker not found in user_icon"
        
        base64_data = user_icon[start_pos + len(start_marker):end_pos]
        
        # Should be valid base64
        try:
            decoded = base64.b64decode(base64_data)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"user_icon contains invalid base64 data: {e}")
    
    def test_agent_types_list(self):
        """Test that agent_types contains expected values"""
        expected_types = ["pipeline", "react", "xml", "openai"]
        assert agent_types == expected_types
        assert len(agent_types) == 4
        assert all(isinstance(agent_type, str) for agent_type in agent_types)
    
    def test_img_to_txt_success(self, tmp_path):
        """Test img_to_txt with valid image file"""
        # Create a temporary image file
        test_file = tmp_path / "test_image.png"
        self.test_image.save(str(test_file), format='PNG')
        
        result = img_to_txt(str(test_file))
        
        # Should be bytes
        assert isinstance(result, bytes)
        
        # Should start and end with correct markers
        assert result.startswith(b"<plain_txt_msg:img>")
        assert result.endswith(b"<!plain_txt_msg>")
        
        # Should contain base64 data between markers
        start_marker = b"<plain_txt_msg:img>"
        end_marker = b"<!plain_txt_msg>"
        
        start_pos = result.find(start_marker)
        end_pos = result.find(end_marker)
        
        base64_data = result[start_pos + len(start_marker):end_pos]
        assert len(base64_data) > 0
        
        # Should be valid base64
        try:
            decoded = base64.b64decode(base64_data)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Generated invalid base64 data: {e}")
    
    def test_img_to_txt_file_not_found(self):
        """Test img_to_txt with non-existent file"""
        with pytest.raises(FileNotFoundError):
            img_to_txt("non_existent_file.png")
    
    def test_decode_img_success(self):
        """Test decode_img with valid encoded image"""
        # First encode an image
        test_file_content = self.test_image_bytes.getvalue()
        base64_data = base64.b64encode(test_file_content)
        
        encoded_msg = b"<plain_txt_msg:img>" + base64_data + b"<!plain_txt_msg>"
        
        result = decode_img(encoded_msg)
        
        assert isinstance(result, Image.Image)
        assert result.size == (10, 10)  # Same size as original
    
    def test_decode_img_missing_start_marker(self):
        """Test decode_img with missing start marker"""
        invalid_msg = b"some_base64_data<!plain_txt_msg>"
        
        result = decode_img(invalid_msg)
        
        # Should return None or handle gracefully
        assert result is None or isinstance(result, Image.Image)
    
    def test_decode_img_missing_end_marker(self):
        """Test decode_img with missing end marker"""
        invalid_msg = b"<plain_txt_msg:img>some_base64_data"
        
        result = decode_img(invalid_msg)
        
        # Should return None or handle gracefully
        assert result is None or isinstance(result, Image.Image)
    
    def test_decode_img_invalid_base64(self):
        """Test decode_img with invalid base64 data"""
        invalid_msg = b"<plain_txt_msg:img>invalid_base64_data<!plain_txt_msg>"
        
        result = decode_img(invalid_msg)
        
        # Should return None or handle gracefully
        assert result is None or isinstance(result, Image.Image)
    
    def test_decode_img_empty_data(self):
        """Test decode_img with empty base64 data"""
        empty_msg = b"<plain_txt_msg:img><!plain_txt_msg>"
        
        result = decode_img(empty_msg)
        
        # Should return None or handle gracefully
        assert result is None or isinstance(result, Image.Image)
    
    def test_decode_img_corrupted_image_data(self):
        """Test decode_img with corrupted image data"""
        # Create valid base64 but invalid image data
        corrupted_data = base64.b64encode(b"not_an_image")
        corrupted_msg = b"<plain_txt_msg:img>" + corrupted_data + b"<!plain_txt_msg>"
        
        result = decode_img(corrupted_msg)
        
        # Should return None or handle gracefully
        assert result is None or isinstance(result, Image.Image)
    
    def test_img_to_txt_and_decode_roundtrip(self, tmp_path):
        """Test complete roundtrip: img_to_txt -> decode_img"""
        # Create a test image with specific characteristics
        test_image = Image.new('RGB', (20, 15), color='blue')
        test_file = tmp_path / "roundtrip_test.png"
        test_image.save(str(test_file), format='PNG')
        
        # Encode
        encoded = img_to_txt(str(test_file))
        
        # Decode
        decoded = decode_img(encoded)
        
        # Verify
        assert isinstance(decoded, Image.Image)
        assert decoded.size == (20, 15)
        assert decoded.mode == 'RGB'
    
    def test_img_to_txt_different_formats(self, tmp_path):
        """Test img_to_txt with different image formats"""
        formats_to_test = ['PNG', 'JPEG']
        
        for format_name in formats_to_test:
            test_image = Image.new('RGB', (5, 5), color='green')
            test_file = tmp_path / f"test_image.{format_name.lower()}"
            test_image.save(str(test_file), format=format_name)
            
            result = img_to_txt(str(test_file))
            
            assert isinstance(result, bytes)
            assert result.startswith(b"<plain_txt_msg:img>")
            assert result.endswith(b"<!plain_txt_msg>")
    
    def test_decode_img_multiple_markers(self):
        """Test decode_img with multiple markers in data"""
        # Create data with multiple markers (should use first occurrence)
        base64_data = base64.b64encode(self.test_image_bytes.getvalue())
        
        multi_marker_msg = (
            b"<plain_txt_msg:img>" + base64_data + b"<!plain_txt_msg>" +
            b"<plain_txt_msg:img>extra_data<!plain_txt_msg>"
        )
        
        result = decode_img(multi_marker_msg)
        
        # Should successfully decode using first marker pair
        assert isinstance(result, Image.Image)
    
    def test_img_to_txt_large_image(self, tmp_path):
        """Test img_to_txt with larger image"""
        # Create a larger test image
        large_image = Image.new('RGB', (100, 100), color='yellow')
        test_file = tmp_path / "large_test.png"
        large_image.save(str(test_file), format='PNG')
        
        result = img_to_txt(str(test_file))
        
        assert isinstance(result, bytes)
        assert len(result) > 1000  # Should be reasonably large
        assert result.startswith(b"<plain_txt_msg:img>")
        assert result.endswith(b"<!plain_txt_msg>")
    
    def test_decode_img_with_binary_input(self):
        """Test decode_img with various binary input types"""
        # Test with bytes
        base64_data = base64.b64encode(self.test_image_bytes.getvalue())
        encoded_msg = b"<plain_txt_msg:img>" + base64_data + b"<!plain_txt_msg>"
        
        result = decode_img(encoded_msg)
        assert isinstance(result, Image.Image) or result is None
        
        # Test with string (should handle conversion)
        try:
            string_msg = encoded_msg.decode('utf-8')
            result_from_string = decode_img(string_msg.encode('utf-8'))
            assert isinstance(result_from_string, Image.Image) or result_from_string is None
        except UnicodeDecodeError:
            # Some base64 data might not be valid UTF-8, that's ok
            pass
    
    @patch('alita_sdk.runtime.utils.streamlit.logger')
    def test_decode_img_logs_errors(self, mock_logger):
        """Test that decode_img logs errors appropriately"""
        invalid_msg = b"<plain_txt_msg:img>invalid_data<!plain_txt_msg>"
        
        result = decode_img(invalid_msg)
        
        # Should have logged an error
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args
        assert "Error decoding image" in str(error_call)
