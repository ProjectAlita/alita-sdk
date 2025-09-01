import pytest
from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit

# Mock toolkits for testing
class MockToolkitWithConfig(BaseIndexerToolkit):
    def __init__(self):
        self.chunking_tool = True
        self.chunking_config = True

class MockToolkitWithoutConfig(BaseIndexerToolkit):
    def __init__(self):
        self.chunking_tool = True
        self.chunking_config = False

@pytest.fixture
def toolkit_with_config():
    return MockToolkitWithConfig()

@pytest.fixture
def toolkit_without_config():
    return MockToolkitWithoutConfig()

def test_chunking_tool_with_config(toolkit_with_config):
    assert toolkit_with_config.chunking_tool is True, "Chunking Tool should be enabled."
    assert toolkit_with_config.chunking_config is True, "Chunking Config should be enabled."

def test_chunking_tool_without_config(toolkit_without_config):
    assert toolkit_without_config.chunking_tool is True, "Chunking Tool should be enabled."
    assert toolkit_without_config.chunking_config is False, "Chunking Config should not be enabled."