import re
import string
from gensim.parsing import remove_stopwords

from ..tools.utils import bytes_to_base64
from langchain_core.messages import HumanMessage


def cleanse_data(document: str) -> str:
    # remove numbers
    document = re.sub(r"\d+", " ", document)

    # print_log("\n",document)
    # remove single characters
    document = " ".join([w for w in document.split() if len(w) > 1])

    # remove punctuations and convert characters to lower case
    document = "".join([
        char.lower()
        for char in document
        if char not in string.punctuation
    ])

    # Remove remove all non-alphanumeric characaters
    document = re.sub(r"\W+", " ", document)

    # Remove 'out of the box' stopwords
    document = remove_stopwords(document)
    # print_log("--- rem ",document)

    # Remove custom keywords
    # for kw in custom_kw:
    #     document = document.replace(kw, "")

    return document

def perform_llm_prediction_for_image_bytes(image_bytes: bytes, llm, prompt: str) -> str:
    """Performs LLM prediction for image content."""
    base64_string = bytes_to_base64(image_bytes)
    result = llm.invoke([
        HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_string}"},
                },
            ]
        )
    ])
    return result.content

def create_temp_file(file_content: bytes):
    import tempfile

    # Automatic cleanup with context manager
    with tempfile.NamedTemporaryFile(mode='w+b', delete=True) as temp_file:
        # Write data to temp file
        temp_file.write(file_content)
        temp_file.flush()  # Ensure data is written

        # Get the file path for operations
        return temp_file.name

def file_to_bytes(filepath):
    """
    Reads a file and returns its content as a bytes object.

    Args:
        filepath (str): The path to the file.

    Returns:
        bytes: The content of the file as a bytes object.
    """
    try:
        with open(filepath, "rb") as f:
            file_content_bytes = f.read()
        return file_content_bytes
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return None