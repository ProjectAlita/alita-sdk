import re
import difflib


def extract_old_new_pairs(file_query: str):
    """
    Extracts old and new content pairs from a file query.
    Parameters:
        file_query (str): The file query containing old and new content.
    Returns:
        list of tuples: A list where each tuple contains (old_content, new_content).
    """
    old_pattern = re.compile(r"OLD <<<<\s*(.*?)\s*>>>> OLD", re.DOTALL)
    new_pattern = re.compile(r"NEW <<<<\s*(.*?)\s*>>>> NEW", re.DOTALL)

    old_contents = old_pattern.findall(file_query)
    new_contents = new_pattern.findall(file_query)

    return list(zip(old_contents, new_contents))


def generate_diff(base_text, target_text, file_path):
    base_lines = base_text.splitlines(keepends=True)
    target_lines = target_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        base_lines, target_lines, fromfile=f"a/{file_path}", tofile=f"b/{file_path}"
    )

    return "".join(diff)

def get_content_from_generator(content_generator):
    def safe_decode(chunk):
        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError:
            return chunk.decode("ascii", errors="backslashreplace")

    return "".join(safe_decode(chunk) for chunk in content_generator)