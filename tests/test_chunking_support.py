import pytest
from alita_sdk.tools.chunking_tool import ChunkingTool

def test_chunking_tool_with_valid_config():
    config = {"chunk_size": 100, "overlap": 10}
    toolkit = ChunkingTool(config)
    result = toolkit.process(data="Sample data for testing")
    assert result is not None
    assert len(result) > 0

def test_chunking_tool_with_invalid_config():
    config = {"chunk_size": -1}  # Invalid chunk size
    with pytest.raises(ValueError):
        ChunkingTool(config)

def test_chunking_tool_missing_config():
    with pytest.raises(KeyError):
        ChunkingTool({})