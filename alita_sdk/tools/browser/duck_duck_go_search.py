from langchain_community.document_loaders import AsyncChromiumLoader
from typing import Type # Add Type import

from langchain_community.document_transformers import BeautifulSoupTransformer
from langchain.text_splitter import CharacterTextSplitter
from duckduckgo_search import DDGS
from langchain_core.tools import BaseTool

from langchain_chroma import Chroma
from pydantic import BaseModel, Field

from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)

class searchPages(BaseModel):
    query: str = Field(..., title="Query text to search pages")

class DuckDuckGoSearch(BaseTool):
    name: str = "DuckDuckGo_Search"
    max_response_size: int = 3000
    description: str = "Searches DuckDuckGo for the query and returns the top 5 results, and them provide summary documents"
    args_schema: Type[BaseModel] = searchPages

    def _run(self, query: str, run_manager=None):
        default_k = 5
        results = DDGS().text(query, max_results=default_k)
        urls = []
        for result in results:
            url = result['href']
            urls.append(url)

        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        docs = text_splitter.split_documents(self.get_page(urls))
        embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        db = Chroma.from_documents(docs, embedding_function)
        docs = db.search(query, "mmr", k=10)
        text = ""
        for doc in docs:
            text += f"\n\n{doc.page_content}"
            if len(text) > self.max_response_size:
                break
        return text

    # retrieves pages and extracts text by tag
    def get_page(self, urls):
        loader = AsyncChromiumLoader(urls)
        html = loader.load()
        bs_transformer = BeautifulSoupTransformer()
        docs_transformed = bs_transformer.transform_documents(html, tags_to_extract=["p"], remove_unwanted_tags=["a"])

        return docs_transformed


