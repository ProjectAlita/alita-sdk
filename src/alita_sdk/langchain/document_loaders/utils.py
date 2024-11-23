import re
import string
from gensim.parsing import remove_stopwords

from ..tools.log import print_log


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
