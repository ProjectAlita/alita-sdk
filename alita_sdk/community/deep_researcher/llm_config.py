from typing import Optional, Any
from dotenv import load_dotenv
from .utils.os import get_env_with_prefix

load_dotenv(override=True)

# Only keeping the necessary environment variable for search provider
SEARCH_PROVIDER = get_env_with_prefix("SEARCH_PROVIDER", "serper")

class LLMConfig:
    def __init__(
        self,
        search_provider: str,
        langchain_llm: Any,
    ):
        self.search_provider = search_provider
        self.reasoning_model = LangchainModelAdapter(langchain_llm)
        self.main_model = LangchainModelAdapter(langchain_llm)
        self.fast_model = LangchainModelAdapter(langchain_llm)


def create_default_config(langchain_llm: Any) -> LLMConfig:
    """Create a default config using a Langchain LLM"""
    return LLMConfig(
        search_provider=SEARCH_PROVIDER,
        langchain_llm=langchain_llm
    )


class LangchainModelAdapter:
    """Adapter class to make Langchain LLMs work with the DeepResearcher framework"""
    
    def __init__(self, langchain_llm):
        self.langchain_llm = langchain_llm
        self._client = type('DummyClient', (), {'_base_url': 'langchain'})()
        
    async def agenerate_response(self, messages, **kwargs):
        """Adapter method to match the expected interface"""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        # Convert message format to Langchain format
        lc_messages = []
        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            if role == 'system':
                lc_messages.append(SystemMessage(content=content))
            elif role == 'user':
                lc_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                lc_messages.append(AIMessage(content=content))
        
        # Use langchain LLM to generate response
        response = await self.langchain_llm.ainvoke(lc_messages)
        
        # Return in format compatible with the existing code
        return type('Response', (), {
            'choices': [
                type('Choice', (), {
                    'message': type('Message', (), {
                        'content': response.content,
                        'role': 'assistant'
                    })
                })
            ]
        })
        
    async def agenerate_text(self, prompt, **kwargs):
        """Simple text completion adapter method"""
        from langchain_core.messages import HumanMessage
        
        response = await self.langchain_llm.ainvoke([HumanMessage(content=prompt)])
        
        # Return in format compatible with the existing code
        return type('Response', (), {
            'choices': [
                type('Choice', (), {
                    'text': response.content
                })
            ]
        })
    
    def supports_json_mode(self):
        """Check if the model supports JSON mode"""
        # Most Langchain LLMs support structured output, so return True by default
        return True
