from ...chunkers.code.constants import get_programming_language, get_file_extension

def search_format(items):
    results = []
    for (doc, score) in items:
        res_chunk = ''
        language = get_programming_language(get_file_extension(doc.metadata["filename"]))
        res_chunk += doc.metadata["filename"] + " -> " + doc.metadata["method_name"] + " (score: " + str(score) + ")"
        res_chunk += "\n\n```" + language.value + "\n"+ doc.page_content + "\n```\n\n"
        results.append(res_chunk)
    return results