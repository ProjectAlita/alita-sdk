import difflib


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