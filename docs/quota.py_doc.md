# quota.py

**Path:** `src/alita_sdk/langchain/tools/quota.py`

## Data Flow

The data flow within `quota.py` revolves around checking directory sizes and performing maintenance on SQLite databases. The primary data elements are directory paths and file sizes. The `quota_check` function takes a dictionary of parameters, extracts the target directory and size limit, and calculates the total size of the directory. If the size exceeds the limit, it returns a dictionary indicating failure. The `sqlite_vacuum` function performs a VACUUM operation on a SQLite database file within a specified directory. Data flows from the input parameters to the file system and back to the output dictionary or log messages.

Example:
```python
params = {"target": "/path/to/dir", "limit": 1000000}
result = quota_check(params)
# result will be {"ok": True} if the directory size is within the limit
```

## Functions Descriptions

### quota_check

The `quota_check` function checks the size of a specified directory and compares it to a given limit. It takes a dictionary `params` with keys `target` (directory path) and `limit` (size limit in bytes). If the directory size exceeds the limit and `enforce` is True, it returns a dictionary with `ok` set to False and includes the limit and total size. Otherwise, it returns `ok` as True.

Example:
```python
def quota_check(params=None, enforce=True, tag="Quota", verbose=False):
    if not isinstance(params, dict):
        return {"ok": True}
    target = params.get("target", None)
    if target is None or not os.path.isdir(target):
        return {"ok": True}
    limit = params.get("limit", None)
    if limit is None or not isinstance(limit, int):
        return {"ok": True}
    total_size = 0
    for root, _, files in os.walk(target):
        for name in files:
            path = os.path.join(root, name)
            total_size += os.path.getsize(path)
    if verbose:
        log.info(
            "[%s] Target size: %s => %s bytes (limit: %s, enforce: %s)",
            tag, target, total_size, limit, enforce,
        )
    if enforce and total_size > limit:
        return {"ok": False, "limit": limit, "total_size": total_size}
    return {"ok": True}
```

### sqlite_vacuum

The `sqlite_vacuum` function performs a VACUUM operation on a SQLite database file located in a specified directory. It takes a dictionary `params` with a key `target` (directory path). If the database file `chroma.sqlite3` exists in the directory, it connects to the database and executes the VACUUM command to optimize the database.

Example:
```python
def sqlite_vacuum(params=None):
    if not isinstance(params, dict):
        return
    target = params.get("target", None)
    if target is None or not os.path.isdir(target):
        return
    db_file = os.path.join(target, "chroma.sqlite3")
    if not os.path.isfile(db_file):
        return
    import sqlite3
    try:
        db_connection = sqlite3.connect(db_file)
        db_cursor = db_connection.cursor()
        db_cursor.execute("VACUUM")
        db_connection.commit()
        db_connection.close()
    except:
        log.exception("Failed to VACUUM: %s", db_file)
```

## Dependencies Used and Their Descriptions

### os

The `os` module is used for interacting with the operating system. It provides functions to check if a path is a directory or file, and to walk through directory trees.

### sqlite3

The `sqlite3` module is used for interacting with SQLite databases. It provides functions to connect to a database, execute SQL commands, and manage transactions.

### log

The `log` module is used for logging messages. It provides functions to log information and exceptions.

## Functional Flow

The functional flow of `quota.py` starts with the `quota_check` function, which is called with parameters specifying a target directory and size limit. The function calculates the total size of the directory and compares it to the limit, logging the result if verbose mode is enabled. If the size exceeds the limit and enforcement is enabled, it returns a failure result. The `sqlite_vacuum` function is called with parameters specifying a target directory. It checks for the existence of a SQLite database file in the directory and performs a VACUUM operation to optimize the database.

## Endpoints Used/Created

There are no explicit endpoints used or created in `quota.py`. The functionality is focused on file system operations and database maintenance.