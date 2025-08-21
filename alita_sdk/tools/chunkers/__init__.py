from .code.codeparser import parse_code_files_for_db
from .sematic.statistical_chunker import statistical_chunker
from .sematic.markdown_chunker import markdown_chunker
from .sematic.proposal_chunker import proposal_chunker
from .sematic.json_chunker import json_chunker
from .models import StatisticalChunkerConfig, MarkdownChunkerConfig, ProposalChunkerConfig

__all__ = {
    'code_parser': parse_code_files_for_db,
    'statistical': statistical_chunker,
    'markdown': markdown_chunker,
    'proposal': proposal_chunker,
    'json': json_chunker
}

__confluence_chunkers__ = {
    'statistical': statistical_chunker,
    'markdown': markdown_chunker,
    'proposal': proposal_chunker
}

__confluence_models__ = {
    'statistical': StatisticalChunkerConfig,
    'markdown': MarkdownChunkerConfig,
    'proposal': ProposalChunkerConfig
}
    