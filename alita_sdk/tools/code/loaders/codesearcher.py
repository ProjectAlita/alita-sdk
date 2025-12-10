from ...chunkers.code.constants import get_programming_language, get_file_extension

def search_format(items):
    results = []
    for (doc, score) in items:
        res_chunk = ''
        language = get_programming_language(get_file_extension(doc.metadata.get("filename", "unknown")))
        method_name = doc.metadata.get("method_name", "text")
        res_chunk += doc.metadata.get("filename", "unknown") + " -> " + method_name + " (score: " + str(score) + ")"
        res_chunk += "\n\n```" + language.value + "\n"+ doc.page_content + "\n```\n\n"
        results.append(res_chunk)
    return results