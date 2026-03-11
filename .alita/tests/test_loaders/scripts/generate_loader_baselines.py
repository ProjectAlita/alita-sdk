#!/usr/bin/env python3
"""
Utility to generate baseline files for document loaders.

This script:
1. Reads all JSON files from the loader's input/ folder
2. Parses the configs array from each input file
3. Uses the tokenize command to generate document chunks based on max_tokens
4. Creates baseline files with page_content and metadata (source, chunk_id)
5. Returns empty array [] for files with only empty content (after trimming)
6. Saves them to the output/ folder with proper naming (e.g., <input_name>_config_<N>.json)

Usage:
    python generate_loader_baselines.py <loader_folder>

Example:
    python generate_loader_baselines.py .alita/tests/test_loaders/AlitaCSVLoader

Input Structure (input/*.json):
    {
        "file_path": "../files/csv_simple.csv",
        "configs": [
            {},
            {"max_tokens": 512, "overlap": 10},
            {"max_tokens": 256, "overlap": 5, "md": true}
        ]
    }

Output Structure (output/*_config_N.json):
    [
        {
            "page_content": "Chunk content...",
            "metadata": {
                "source": ".alita/tests/test_loaders/LoaderName/files/file.txt",
                "chunk_id": 1
            }
        }
    ]
    
    Note: Returns empty array [] if all content is empty after trimming.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def tokenize_file(file_path: Path, max_tokens: int = None, overlap: int = 10, md: bool = False) -> List[str]:
    """
    Tokenize a file using the run_tests.py tokenize command.
    
    Args:
        file_path: Path to the file to tokenize
        max_tokens: Maximum tokens per chunk (if None, no chunking)
        overlap: Token overlap between chunks
        md: If True, replace '\\n\\n' with '  \\n' before chunking (markdown mode)
    
    Returns:
        List of chunk strings (or token strings if no chunking)
    """
    cmd = [
        "python",
        ".alita/tests/test_loaders/run_tests.py",
        "tokenize",
        "-f",
        str(file_path)
    ]
    
    if max_tokens is not None:
        cmd.extend(["-m", str(max_tokens), "-o", str(overlap)])
    
    if md:
        cmd.append("-md")
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def generate_baseline(
    file_path: Path,
    config: Dict[str, Any],
    output_path: Path,
    force_md: bool = None
) -> None:
    """
    Generate a baseline file for a given input file and config.
    
    Args:
        file_path: Path to the input file
        config: Configuration dict (may contain max_tokens, overlap, md, etc.)
        output_path: Path to save the baseline JSON
        force_md: If provided, override the md setting from config
    """
    # Extract tokenization parameters from config
    # Use production default of 512 tokens if not specified (DEFAULT_ALLOWED_BASE)
    max_tokens = config.get("max_tokens", 512)
    overlap = config.get("overlap", 10)
    md = force_md if force_md is not None else config.get("md", False)
    
    # Calculate relative path for source field (relative to current working directory)
    try:
        relative_source = file_path.relative_to(Path.cwd())
    except ValueError:
        # If file is outside cwd, use absolute path
        relative_source = file_path
    
    # Tokenize the file with chunking
    chunks = tokenize_file(file_path, max_tokens=max_tokens, overlap=overlap, md=md)
    
    # Check if all chunks are empty (trimmed)
    non_empty_chunks = [chunk for chunk in chunks if chunk.strip()]
    if not non_empty_chunks:
        # Return empty array for empty content
        documents = []
    else:
        # Create documents with chunk_id and source in metadata
        documents = []
        for idx, chunk_text in enumerate(chunks, start=1):
            doc = {
                "page_content": chunk_text,
                "metadata": {
                    "source": str(relative_source),
                    "chunk_id": idx
                }
            }
            documents.append(doc)
    
    # Save baseline
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Created {output_path.name} ({len(documents)} document(s))")


def process_loader_folder(loader_folder: Path, force_md: bool = None) -> None:
    """
    Process a loader folder to generate baselines for all input files.
    
    Args:
        loader_folder: Path to the loader folder (contains input/ and files/ subfolders)
        force_md: If provided, override the md setting from all configs
    """
    input_folder = loader_folder / "input"
    output_folder = loader_folder / "output"
    
    if not input_folder.exists():
        print(f"❌ Input folder not found: {input_folder}")
        sys.exit(1)
    
    # Find all input JSON files
    input_files = sorted(input_folder.glob("*.json"))
    
    if not input_files:
        print(f"❌ No input JSON files found in {input_folder}")
        sys.exit(1)
    
    print(f"📋 Found {len(input_files)} input file(s)")
    print(f"📂 Output folder: {output_folder}")
    print()
    
    # Process each input file
    for input_file in input_files:
        print(f"📝 Processing {input_file.name}...")
        
        # Load input JSON
        with open(input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        
        # Get file path (relative to input folder)
        relative_file_path = input_data.get("file_path")
        if not relative_file_path:
            print(f"  ⚠️  No file_path found in {input_file.name}, skipping")
            continue
        
        # Resolve absolute path (relative to input folder)
        file_path = (input_folder / relative_file_path).resolve()
        
        if not file_path.exists():
            print(f"  ⚠️  File not found: {file_path}, skipping")
            continue
        
        # Get configs
        configs = input_data.get("configs", [])
        if not configs:
            print(f"  ⚠️  No configs found in {input_file.name}, skipping")
            continue
        
        print(f"  📄 File: {file_path.name}")
        print(f"  🔧 Configs: {len(configs)}")
        
        # Process each config
        for config_idx, config in enumerate(configs):
            # Generate output filename
            input_stem = input_file.stem  # e.g., "csv_simple"
            output_filename = f"{input_stem}_config_{config_idx}.json"
            output_path = output_folder / output_filename
            
            # Generate baseline
            try:
                generate_baseline(file_path, config, output_path, force_md=force_md)
            except Exception as e:
                print(f"  ❌ Failed to generate {output_filename}: {e}")
        
        print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python generate_loader_baselines.py <loader_folder> [-md]")
        print()
        print("Options:")
        print("  -md    Enable markdown mode (replace '\\n\\n' with '  \\n' before chunking)")
        print()
        print("Example:")
        print("  python generate_loader_baselines.py .alita/tests/test_loaders/AlitaCSVLoader")
        print("  python generate_loader_baselines.py .alita/tests/test_loaders/AlitaTextLoader -md")
        sys.exit(1)
    
    loader_folder = Path(sys.argv[1])
    
    # Check for -md flag
    force_md = "-md" in sys.argv[2:] if len(sys.argv) > 2 else None
    
    if not loader_folder.exists():
        print(f"❌ Loader folder not found: {loader_folder}")
        sys.exit(1)
    
    print(f"🔍 Processing loader: {loader_folder.name}")
    if force_md:
        print(f"🔧 Markdown mode: enabled")
    print()
    
    process_loader_folder(loader_folder, force_md=force_md)
    
    print("✅ Baseline generation complete!")


if __name__ == "__main__":
    main()
