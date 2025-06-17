import os
from enum import Enum
import langchain.text_splitter as text_splitter

# We need to port more language from here
# https://github.com/grantjenks/py-tree-sitter-languages?tab=readme-ov-file

class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    GO = "go"
    RUST = "rust"
    KOTLIN = "kotlin"
    C_SHARP = "c_sharp"
    OBJECTIVE_C = "objective_c"
    SCALA = "scala"
    LUA = "lua"
    HASKELL = "haskell"
    RUBY = "ruby"
    UNKNOWN = "unknown"



def get_programming_language(file_extension: str) -> Language:
    """
    Returns the programming language based on the provided file extension.

    Args:
        file_extension (str): The file extension to determine the programming language of.

    Returns:
        Language: The programming language corresponding to the file extension. If the file extension is not found
        in the language mapping, returns Language.UNKNOWN.
    """
    language_mapping = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".mjs": Language.JAVASCRIPT,
        ".cjs": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".java": Language.JAVA,
        ".kt": Language.KOTLIN,
        ".rs": Language.RUST,
        ".go": Language.GO,
        ".cpp": Language.CPP,
        ".c": Language.C,
        ".cs": Language.C_SHARP,
        ".hs": Language.HASKELL,
        ".rb": Language.RUBY
    }
    return language_mapping.get(file_extension, Language.UNKNOWN)

image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp", ".ico", ".tiff", ".tif", ".heic", ".heif", ".avif", ".pdf", '.lock']
default_skip = [".gitignore", ".gitattributes", ".gitmodules", ".gitkeep", ".DS_Store", ".editorconfig", ".npmignore", 'LICENSE',
                ".yarnignore", ".dockerignore", ".prettierignore", ".eslintignore", ".stylelintignore", 
                ".gitlab-ci.yml", ".travis.yml", ".circleci", ".github", ".vscode", ".idea", 
                ".git", ".hg", ".svn", ".bzr", ".npmrc", ".yarnrc", ".yarnrc.yml", ".yarnrc.yaml"]

def get_file_extension(file_name: str) -> str:
    """
    Returns the extension of a file from its given name.

    Parameters:
        file_name (str): The name of the file.

    Returns:
        str: The extension of the file.

    """
    return os.path.splitext(file_name)[-1]


def get_langchain_language(language: Language):
    if language == Language.PYTHON:
        return text_splitter.Language.PYTHON
    elif language == Language.JAVASCRIPT:
        return text_splitter.Language.JS
    elif language == Language.TYPESCRIPT:
        return text_splitter.Language.TS
    elif language == Language.JAVA:
        return text_splitter.Language.JAVA
    elif language == Language.KOTLIN:
        return text_splitter.Language.KOTLIN
    elif language == Language.RUST:
        return text_splitter.Language.RUST
    elif language == Language.GO:
        return text_splitter.Language.GO
    elif language == Language.CPP:
        return text_splitter.Language.CPP
    elif language == Language.C_SHARP:
        return text_splitter.Language.CSHARP
    elif language == Language.HASKELL:
        return text_splitter.Language.HASKELL
    elif language == Language.RUBY:
        return text_splitter.Language.RUBY
    else:
        return None