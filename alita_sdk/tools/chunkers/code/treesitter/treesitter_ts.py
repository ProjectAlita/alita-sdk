from ..constants import Language
from .treesitter import Treesitter
from .treesitter_registry import TreesitterRegistry


class TreesitterTypescript(Treesitter):
    def __init__(self):
        super().__init__(
            Language.TYPESCRIPT, "function_declaration", "identifier", "comment"
        )


TreesitterRegistry.register_treesitter(Language.TYPESCRIPT, TreesitterTypescript)
