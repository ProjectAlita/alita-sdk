# index_data

The `index_data` method orchestrates the full pipeline for indexing documents into a vector store collection.  
It manages document loading, optional index cleaning, dependency processing, chunking, metadata cleaning, and final storage.  
This method is designed to be extensible and robust for various toolkits and indexing requirements.

---

### 1. Index Cleaning

The method calls `_clean_index` (according to arguments) to remove all existing data from the target collection.

---

### 2. Document Loading

`_base_loader` is called to load the initial high-level data for **base documents** from the data source.  
The toolkit is expected to handle empty sources or errors gracefully.

---

### 3. Duplicate Removal

The method `_reduce_duplicates` is responsible for filtering out already-indexed documents based on previously loaded high-level data (mainly value of key 'updated_on' is used).

---

### 4. Data Extension

This stage is to update or enriche only non-duplicated documents.  
Resource- and time-consuming operations are expected to be performed here via `_extend_data`.  
The type of documents (file extension) and raw content (bytes) of base document should be defined at this stage.

---

### 5. Dependency Collection

Calls `_collect_dependencies` to extract all **dependent documents** on or attached to the base one.  
The type of documents (file extension) and raw content (bytes) of dependent document should be defined at this stage.

---

### 6. Chunking/Parsing

Calls `_apply_loaders_chunkers` to process and split the content of all previously collected **base and dependent documents** using the specified chunking tool and configuration.
At this stage chunking config is used. Settings for particular document types (file extensions) are used to override default one for corresponding loaders/chunkers.

---

### 7. Metadata Cleaning

Calls `_clean_metadata` to remove unnecessary or sensitive metadata fields from each document.  
This prevents leaking sensitive information and reduces index size.

---

### 8. Saving to Index

Calls `_save_index` to persist the processed documents into the vector store, using progress reporting if configured.  
Corner case: Handles empty document lists and ensures atomicity of the save operation.

---

## Common Parameters for `index_data`

- `collection_suffix` (`str`):  
  Suffix for the collection name (max 7 characters) used to separate datasets.

- `progress_step` (`Optional[int]`):  
  Optional step size for progress reporting during indexing (default: 10, range: 0-100).

- `clean_index` (`Optional[bool]`):  
  Optional flag to enforce cleaning the existing index before indexing new data (default: `False`).

+ `chunking_tool` (`Optional[str]`):  
  Name of the chunking tool to use for splitting documents before indexing (default: `None`).  
  Example: `"recursive_text_splitter"`, `"pdf_parser"`, or `"markdown_chunker"`.
+ `chunking_config` (`Optional[dict]`):  
  Configuration settings for the chunking tool, keyed by file extension (default: empty dict).   
  Example: {".pdf": {"mode": "page", "chunk_size": 1000}, ".docx": {"mode": "paragraph"}, ".md": {"chunk_size": 333}}

---

## Toolkit Specific Parameters for `index_data`

Other extra parameters (for particular toolkit needs) can be provided by the implementation of `_index_tool_params()`.
