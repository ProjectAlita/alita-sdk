
import numpy as np
from typing import Generator, Optional, List
from logging import getLogger
from langchain.schema import Document
from langchain.text_splitter import TokenTextSplitter
from tqdm.auto import tqdm

logger = getLogger(__name__)

from .base import Chunk
from ..utils import tiktoken_length


def _encode_documents(embeddings: 'BaseModel', docs: List[str]) -> np.ndarray: # type: ignore
    """
    Encodes a list of documents into embeddings. If the number of documents
    exceeds 2000, the documents are split into batches to avoid overloading
    the encoder. OpenAI has a limit of len(array) < 2048.

    :param docs: List of text documents to be encoded.
    :return: A numpy array of embeddings for the given documents.
    """
    max_docs_per_batch = 2000
    _embeddings = []
    logger.info(f"Encoding {len(docs)} documents.")
    for i in range(0, len(docs), max_docs_per_batch):
        batch_docs = docs[i : i + max_docs_per_batch]
        try:
            batch_embeddings = embeddings.embed_documents(batch_docs)
            _embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Error encoding documents {batch_docs}: {e}")
            raise
    logger.info(f"Encoded {len(_embeddings)} embeddings.")
    return np.array(_embeddings)

def _calculate_similarity_scores(encoded_docs: np.ndarray, window_size: int) -> List[float]:
        raw_similarities = []
        for idx in range(1, len(encoded_docs)):
            window_start = max(0, idx - window_size)
            cumulative_context = np.mean(encoded_docs[window_start:idx], axis=0)
            curr_sim_score = np.dot(cumulative_context, encoded_docs[idx]) / (
                np.linalg.norm(cumulative_context) * np.linalg.norm(encoded_docs[idx])
                + 1e-10
            )
            raw_similarities.append(curr_sim_score)
        return raw_similarities

def _find_split_indices(
        similarities: List[float], calculated_threshold: float
    ) -> List[int]:
        split_indices = []
        for idx, score in enumerate(similarities):
            logger.debug(f"Similarity score at index {idx}: {score}")
            if score < calculated_threshold:
                logger.debug(
                    f"Adding to split_indices due to score < threshold: "
                    f"{score} < {calculated_threshold}"
                )
                # Chunk after the document at idx
                split_indices.append(idx + 1)
        return split_indices
    
def _find_optimal_threshold(docs: List[str], similarity_scores: List[float], 
                            min_split_tokens:int = 100, 
                            max_split_tokens:int = 300,
                            split_tokens_tolerance: int = 10,
                            threshold_adjustment: float = 0.01
                            ) -> float:
    token_counts = [tiktoken_length(doc) for doc in docs]
    cumulative_token_counts = np.cumsum([0] + token_counts)

    # Analyze the distribution of similarity scores to set initial bounds
    median_score = np.median(similarity_scores)
    std_dev = np.std(similarity_scores)

    # Set initial bounds based on median and standard deviation
    low = max(0.0, float(median_score - std_dev))
    high = min(1.0, float(median_score + std_dev))

    iteration = 0
    median_tokens = 0
    calculated_threshold = 0.0
    while low <= high:
        calculated_threshold = (low + high) / 2
        split_indices = _find_split_indices(similarity_scores, calculated_threshold)
        logger.debug(f"Iteration {iteration}: Trying threshold: {calculated_threshold}")

        # Calculate the token counts for each split using the cumulative sums
        split_token_counts = [
            cumulative_token_counts[end] - cumulative_token_counts[start]
            for start, end in zip(
                [0] + split_indices, split_indices + [len(token_counts)]
            )
        ]
        
        # Calculate the median token count for the chunks
        median_tokens = np.median(split_token_counts)
        logger.debug(
            f"Iteration {iteration}: Median tokens per split: {median_tokens}"
        )
        if (
            min_split_tokens - split_tokens_tolerance
            <= median_tokens
            <= max_split_tokens + split_tokens_tolerance
        ):
            logger.debug("Median tokens in target range. Stopping iteration.")
            break
        elif median_tokens < min_split_tokens:
            high = calculated_threshold - threshold_adjustment
            logger.debug(f"Iteration {iteration}: Adjusting high to {high}")
        else:
            low = calculated_threshold + threshold_adjustment
            logger.debug(f"Iteration {iteration}: Adjusting low to {low}")
        iteration += 1

    logger.debug(
        f"Optimal threshold {calculated_threshold} found "
        f"with median tokens ({median_tokens}) in target range "
        f"({min_split_tokens}-{max_split_tokens})."
    )

    return calculated_threshold

def _find_split_indices(similarities: List[float], calculated_threshold: float) -> List[int]:
    split_indices = []
    for idx, score in enumerate(similarities):
        logger.debug(f"Similarity score at index {idx}: {score}")
        if score < calculated_threshold:
            logger.debug(
                f"Adding to split_indices due to score < threshold: "
                f"{score} < {calculated_threshold}"
            )
            # Chunk after the document at idx
            split_indices.append(idx + 1)
    return split_indices


def _split_documents(docs: List[str], split_indices: List[int], similarities: List[float],
                     max_split_tokens: int = 300, min_split_tokens: int = 100, 
                     ) -> List[Chunk]:
    """
    This method iterates through each document, appending it to the current split
    until it either reaches a split point (determined by split_indices) or exceeds
    the maximum token limit for a split (max_split_tokens).
    When a document causes the current token count to exceed this limit,
    or when a split point is reached and the minimum token requirement is met,
    the current split is finalized and added to the List of chunks.
    """
    token_counts = [tiktoken_length(doc) for doc in docs]
    chunks, current_split = [], []
    current_tokens_count = 0

    # Statistics
    chunks_by_threshold = 0
    chunks_by_max_chunk_size = 0
    chunks_by_last_split = 0

    for doc_idx, doc in enumerate(docs):
        doc_token_count = token_counts[doc_idx]
        logger.debug(f"Accumulative token count: {current_tokens_count} tokens")
        logger.debug(f"Document token count: {doc_token_count} tokens")
        # Check if current index is a split point based on similarity
        if doc_idx + 1 in split_indices:
            if (
                min_split_tokens
                <= current_tokens_count + doc_token_count
                < max_split_tokens
            ):
                # Include the current document before splitting
                # if it doesn't exceed the max limit
                current_split.append(doc)
                current_tokens_count += doc_token_count

                triggered_score = (
                    similarities[doc_idx] if doc_idx < len(similarities) else None
                )
                chunks.append(
                    Chunk(
                        splits=current_split.copy(),
                        is_triggered=True,
                        triggered_score=triggered_score,
                        token_count=current_tokens_count,
                    )
                )
                logger.debug(
                    f"Chunk finalized with {current_tokens_count} tokens due to "
                    f"threshold {triggered_score}."
                )
                current_split, current_tokens_count = [], 0
                chunks_by_threshold += 1
                continue  # Move to the next document after splitting

        # Check if adding the current document exceeds the max token limit
        if current_tokens_count + doc_token_count > max_split_tokens:
            if current_tokens_count >= min_split_tokens:
                chunks.append(
                    Chunk(
                        splits=current_split.copy(),
                        is_triggered=False,
                        triggered_score=None,
                        token_count=current_tokens_count,
                    )
                )
                chunks_by_max_chunk_size += 1
                logger.debug(
                    f"Chink finalized with {current_tokens_count} tokens due to "
                    f"exceeding token limit of {max_split_tokens}."
                )
                current_split, current_tokens_count = [], 0

        current_split.append(doc)
        current_tokens_count += doc_token_count

    # Handle the last split
    if current_split:
        chunks.append(
            Chunk(
                splits=current_split.copy(),
                is_triggered=False,
                triggered_score=None,
                token_count=current_tokens_count,
            )
        )
        chunks_by_last_split += 1
        logger.debug(
            f"Final split added with {current_tokens_count} "
            "tokens due to remaining documents."
        )

    # Validation to ensure no tokens are lost during the split
    original_token_count = sum(token_counts)
    split_token_count = sum(
        [tiktoken_length(doc) for split in chunks for doc in split.splits]
    )
    if original_token_count != split_token_count:
        logger.error(
            f"Token count mismatch: {original_token_count} != {split_token_count}"
        )
        raise ValueError(
            f"Token count mismatch: {original_token_count} != {split_token_count}"
        )

    return chunks
        

def statistical_chunker(file_content_generator: Generator[Document, None, None], config: dict, *args, **kwargs) -> Generator[str, None, None]:
    logger.info(config)
    embedding = config.get('embedding')
    if embedding is None:
        raise ImportError("Could not import the required module 'alita_sdk.langchain.interfaces.llm_processor'.")
    max_tokens_doc: int = config.get("max_doc_size", 300)
    batch_size: int = config.get("batch_size", 64)
    window_size: int = config.get("window_size", 5)
    dynamic_threshold: bool = config.get("dynamic_threshold", True)
    min_split_tokens: int = config.get("min_split_tokens", 100)
    max_split_tokens: int = config.get("max_split_tokens", 300)
    split_tokens_tolerance: int = config.get("split_tokens_tolerance", 10)
    threshold_adjustment: float = config.get("threshold_adjustment", 0.01)
    score_threshold: float = config.get("score_threshold", 0.5)
    docs_no = 0
    for doc in file_content_generator:
        docs_no+=1
        logger.info(f"Processing document {docs_no}.")
        try:
            doc_metadata = doc.metadata
            doc_content = doc.page_content
            last_chunk: Optional[Chunk] = None
            splits = TokenTextSplitter(encoding_name='cl100k_base', 
                                    chunk_size=max_tokens_doc, chunk_overlap=0
                                    ).split_text(doc_content)
            logger.info(f"Splitting {len(splits)} documents.")
            chunk_id = 0
            for i in tqdm(range(0, len(splits), batch_size)):
                batch_splits = splits[i : i + batch_size]
                if last_chunk is not None:
                    batch_splits = last_chunk.splits + batch_splits
                
                encoded_splits = _encode_documents(embedding, batch_splits)
                
                similarities = _calculate_similarity_scores(encoded_splits, window_size)

                if dynamic_threshold:
                    calculated_threshold = _find_optimal_threshold(
                        batch_splits, similarities, min_split_tokens, 
                        max_split_tokens, split_tokens_tolerance, 
                        threshold_adjustment
                    )
                else:
                    calculated_threshold = score_threshold
                
                split_indices = _find_split_indices(
                    similarities=similarities, 
                    calculated_threshold=calculated_threshold
                )

                doc_chunks = _split_documents(
                    docs=batch_splits,
                    split_indices=split_indices,
                    similarities=similarities,
                )
                for chunk in doc_chunks:
                    chunk_id += 1
                    metadata = doc_metadata.copy()
                    metadata['chunk_id'] = chunk_id
                    metadata['chunk_token_count'] = chunk.token_count
                    metadata['chunk_type'] = "document"
                    last_chunk = chunk
                    logger.info(f"Chunk {chunk_id} created with {chunk.token_count} tokens.")
                    logger.info(f"Chunk metadata: {metadata}")
                    yield Document(
                        page_content=chunk.content,
                        metadata=metadata
                    )
        except Exception as e:
            from traceback import format_exc
            logger.error(f"Error: {format_exc()}")
            raise e
