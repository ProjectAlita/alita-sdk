# pgvector_search.py

**Path:** `src/alita_sdk/tools/pgvector_search.py`

## Data Flow

The data flow within `pgvector_search.py` revolves around the interaction with a PostgreSQL database to perform vector search operations. The data originates from the PostgreSQL database, where it is stored in collections/tables. The data is then retrieved, processed, and returned to the user based on the search queries and filters applied.

For example, in the `full_text_search` method, the data flow can be described as follows:

1. The method receives the search query and field name as input parameters.
2. A connection to the PostgreSQL database is established using the `_get_connection` method.
3. The search query is executed on the specified field in the collection/table using SQL commands.
4. The results are fetched from the database and returned as a list of dictionaries.

```python
# Example of data flow in full_text_search method
conn = self._get_connection()
cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

try:
    sql = f"""
        SELECT 
            id, 
            (ts_rank(to_tsvector(%s, cmetadata->>%s), plainto_tsquery(%s, %s))) as text_score
        FROM 
            {self.collection_name}
        WHERE 
            cmetadata ? %s
            AND to_tsvector(%s, cmetadata->>%s) @@ plainto_tsquery(%s, %s)
        ORDER BY 
            text_score DESC
        LIMIT %s
    """
    cursor.execute(
        sql, 
        (
            self.language, field_name, self.language, query, 
            field_name, self.language, field_name, 
            self.language, query, limit
        )
    )
    results = cursor.fetchall()
    return [dict(row) for row in results]
except Exception as e:
    logger.error(f"Full-text search error: {str(e)}")
    conn.rollback()
    return []
finally:
    cursor.close()
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `PGVectorSearch` class with the PostgreSQL connection string, collection name, and language for full-text search. It sets up the initial state of the object.

### `_get_connection`

The `_get_connection` method establishes and returns a connection to the PostgreSQL database. If the connection is already open, it reuses it; otherwise, it creates a new connection.

### `_close_connection`

The `_close_connection` method closes the PostgreSQL connection if it is open.

### `_process_filter_condition`

The `_process_filter_condition` method processes a single filter condition and converts it into an SQL condition string with parameters for parameterized queries. It handles various operators like `$eq`, `$ne`, `$lt`, `$lte`, `$gt`, `$gte`, `$in`, `$nin`, `$between`, `$exists`, `$like`, `$ilike`, `$and`, and `$or`.

### `_process_filter`

The `_process_filter` method processes a filter dictionary into an SQL WHERE clause with parameters for parameterized queries. It supports logical operators like `$and` and `$or`.

### `full_text_search`

The `full_text_search` method performs a full-text search on a specific field in the collection/table. It constructs and executes an SQL query to search for the specified query in the given field and returns the results as a list of dictionaries.

### `get_documents_by_ids`

The `get_documents_by_ids` method retrieves documents from the collection/table by their IDs. It constructs and executes an SQL query to fetch the documents with the specified IDs and returns them as a dictionary mapping IDs to document data.

### `search_with_filters`

The `search_with_filters` method performs a search with filters on the collection/table. It constructs and executes an SQL query based on the search query and filter dictionary, and returns the results as a list of dictionaries.

### `__del__`

The `__del__` method is a destructor that ensures the PostgreSQL connection is closed when the `PGVectorSearch` object is deleted.

## Dependencies Used and Their Descriptions

### `psycopg2`

`psycopg2` is a PostgreSQL adapter for Python. It is used to establish connections to the PostgreSQL database, execute SQL queries, and fetch results. The `psycopg2.extras` module provides additional features like the `RealDictCursor` for fetching query results as dictionaries.

### `json`

The `json` module is used to handle JSON data. It is used to convert Python objects to JSON strings and vice versa, particularly when dealing with JSON fields in the PostgreSQL database.

### `logging`

The `logging` module is used for logging error messages and other information. It helps in debugging and monitoring the application's behavior.

### `typing`

The `typing` module provides type hints for function arguments and return values. It is used to specify the expected types of parameters and return values for better code readability and maintainability.

## Functional Flow

The functional flow of `pgvector_search.py` involves initializing the `PGVectorSearch` class, establishing a connection to the PostgreSQL database, and performing various search operations based on the methods called. The sequence of operations is as follows:

1. Initialize the `PGVectorSearch` object with the connection string, collection name, and language.
2. Establish a connection to the PostgreSQL database using the `_get_connection` method.
3. Perform search operations like `full_text_search`, `get_documents_by_ids`, and `search_with_filters` based on the user's input.
4. Process filter conditions and construct SQL queries using `_process_filter_condition` and `_process_filter` methods.
5. Execute the SQL queries and fetch the results from the database.
6. Return the results to the user in the form of dictionaries or lists of dictionaries.
7. Close the database connection when the object is deleted using the `__del__` method.

## Endpoints Used/Created

The `pgvector_search.py` file does not explicitly define or call any endpoints. It interacts directly with the PostgreSQL database using SQL queries executed through the `psycopg2` library.