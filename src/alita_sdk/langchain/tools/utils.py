import base64
import io
import json
import difflib
import re
import threading

from PIL.Image import Image
from openpyxl.cell.text import InlineFont
from openpyxl.cell.rich_text import TextBlock, CellRichText


def tokenize(s):
    return re.split(r'\s+', s)


def untokenize(ts):
    return ' '.join(ts)


def untokenize_cellrichtext(ts):
    result = CellRichText()
    #
    if not ts:
        return result
    #
    result.append(ts[0])
    #
    for item in ts[1:]:
        result.append(' ')
        result.append(item)
    #
    return result


def equalize(s1, s2):
    l1 = tokenize(s1)
    l2 = tokenize(s2)
    res1 = []
    res2 = []
    prev = difflib.Match(0, 0, 0)
    for match in difflib.SequenceMatcher(a=l1, b=l2).get_matching_blocks():
        if prev.a + prev.size != match.a:
            for i in range(prev.a + prev.size, match.a):
                res2 += ['_' * len(l1[i])]
            res1 += l1[prev.a + prev.size:match.a]
        if prev.b + prev.size != match.b:
            for i in range(prev.b + prev.size, match.b):
                res1 += ['_' * len(l2[i])]
            res2 += l2[prev.b + prev.size:match.b]
        res1 += l1[match.a:match.a + match.size]
        res2 += l2[match.b:match.b + match.size]
        prev = match
    return untokenize(res1), untokenize(res2)


def equalize_markdown(s1, s2):
    l1 = tokenize(s1)
    l2 = tokenize(s2)
    res1 = []
    res2 = []
    prev = difflib.Match(0, 0, 0)
    for match in difflib.SequenceMatcher(a=l1, b=l2).get_matching_blocks():
        # Handle removed text in s1
        if prev.a + prev.size != match.a:
            for i in range(prev.a + prev.size, match.a):
                if len(l1[i]):
                    res1 += ['~~' + l1[i] + '~~']  # Removed text marked with strikethrough

        # Handle added text in s2
        if prev.b + prev.size != match.b:
            for i in range(prev.b + prev.size, match.b):
                if len(l2[i]):
                    res2 += ['**' + l2[i] + '**']  # Added text in bold

        # Common text
        res1 += l1[match.a:match.a + match.size]
        res2 += l2[match.b:match.b + match.size]
        prev = match

    return untokenize(res1), untokenize(res2)


def equalize_openpyxl(s1, s2):
    l1 = tokenize(s1)
    l2 = tokenize(s2)
    #
    res1 = []
    res2 = []
    #
    strikethrough = InlineFont(strike=True)
    bold = InlineFont(b=True)
    #
    prev = difflib.Match(0, 0, 0)
    for match in difflib.SequenceMatcher(a=l1, b=l2).get_matching_blocks():
        # Handle removed text in s1
        if prev.a + prev.size != match.a:
            for i in range(prev.a + prev.size, match.a):
                if len(l1[i]):
                    res1.append(TextBlock(strikethrough, l1[i]))  # Removed text
        # Handle added text in s2
        if prev.b + prev.size != match.b:
            for i in range(prev.b + prev.size, match.b):
                if len(l2[i]):
                    res2.append(TextBlock(bold, l2[i]))  # Added text
        # Common text
        res1 += l1[match.a:match.a + match.size]
        res2 += l2[match.b:match.b + match.size]
        prev = match
    #
    return untokenize_cellrichtext(res1), untokenize_cellrichtext(res2)


def replace_source(document, source_replacers, keys=None):
    """ Replace source start(s) """
    if keys is None:
        keys = ["source"]
    #
    for key in keys:
        if key not in document.metadata:
            continue
        #
        document_source = document.metadata[key]
        #
        fixed_source = document_source
        for replace_from, replace_to in source_replacers.items():
            fixed_source = fixed_source.replace(replace_from, replace_to, 1)
        #
        document.metadata[key] = fixed_source


def unpack_json(json_data):
    if (isinstance(json_data, str)):
        if '```json' in json_data:
            json_data = json_data.replace('```json', '').replace('```', '')
            return json.loads(json_data)
        return json.loads(json_data)
    elif (isinstance(json_data, dict)):
        return json_data
    else:
        raise ValueError("Wrong type of json_data")


def download_nltk(target, force=False):
    """ Download NLTK punkt """
    from . import state  # pylint: disable=C0415
    #
    if state.nltk_punkt_downloaded and not force:
        return
    #
    import ssl  # pylint: disable=C0415
    #
    try:
        _create_unverified_https_context = ssl._create_unverified_context  # pylint: disable=W0212
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context  # pylint: disable=W0212
    #
    import os  # pylint: disable=C0415
    import nltk  # pylint: disable=C0415,E0401
    import nltk.downloader  # pylint: disable=C0415,E0401
    #
    os.makedirs(target, exist_ok=True)
    #
    nltk.downloader._downloader._download_dir = target  # pylint: disable=W0212
    nltk.data.path = [target]
    #
    nltk_packages = ["all"]
    #
    for package in nltk_packages:
        nltk.download(package, download_dir=target)
    #
    state.nltk_punkt_downloaded = True

def bytes_to_base64(bt: bytes) -> str:
    return base64.b64encode(bt).decode('utf-8')

def path_to_base64(path) -> str:
    with open(path, 'rb') as binary_file:
        return base64.b64encode(binary_file.read()).decode('utf-8')

def image_to_byte_array(image: Image) -> bytes:
    raw_bytes = io.BytesIO()
    image.save(raw_bytes, format='PNG')
    return raw_bytes.getvalue()


class LockedIterator:
    """ Make iterator thread-safe """

    def __init__(self, iterator):
        self.iterator = iterator
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self.lock:
            return self.iterator.__next__()
