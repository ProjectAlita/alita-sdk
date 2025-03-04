# pgvector_search.py

**Path:** `src/alita_sdk/tools/pgvector_search.py`

## Data Flow

The data flow within the `pgvector_search.py` file revolves around the interaction with a PostgreSQL database to perform vector search operations. The data originates from the PostgreSQL database, where it is stored in collections/tables. The data is then retrieved, processed, and returned to the user based on the search queries and filters applied.

The primary data elements include the connection string, collection name, language for full-text search, and various search parameters. These elements are used to establish a connection to the database, execute search queries, and process the results.

For example, in the `full_text_search` method, the data flow can be traced as follows:

1. The method receives the field name, search query, and limit as input parameters.
2. A connection to the PostgreSQL database is established using the `_get_connection` method.
3. A SQL query is constructed to perform a full-text search on the specified field.
4. The query is executed, and the results are fetched from the database.
5. The results are processed and returned as a list of dictionaries.

```python
# Example of data flow in full_text_search method
conn = self._get_connection()  # Establish connection to the database
cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # Create a cursor for executing the query

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
    results = cursor.fetchall()  # Fetch the results from the database
    return [dict(row) for row in results]  # Process and return the results
finally:
    cursor.close()  # Close the cursor
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `PGVectorSearch` class with the provided connection string, collection name, and language for full-text search. It sets up the necessary instance variables and prepares the class for database operations.

**Parameters:**
- `connection_string` (str): The PostgreSQL connection string.
- `collection_name` (str): The name of the collection/table to search.
- `language` (str): The language for full-text search (default: 'english').

### `_get_connection`

The `_get_connection` method establishes a connection to the PostgreSQL database using the provided connection string. If a connection already exists and is open, it returns the existing connection. Otherwise, it creates a new connection.

**Returns:**
- `psycopg2.connection`: The PostgreSQL connection object.

### `_close_connection`

The `_close_connection` method closes the PostgreSQL connection if it is open. It ensures that the connection is properly closed and resources are released.

### `_process_filter_condition`

The `_process_filter_condition` method processes a single filter condition and converts it into an SQL condition string. It handles various operators such as `$eq`, `$ne`, `$lt`, `$lte`, `$gt`, `$gte`, `$in`, `$nin`, `$between`, `$exists`, `$like`, `$ilike`, `$and`, and `$or`.

**Parameters:**
- `key` (str): The field name or operator.
- `value` (Any): The filter value or nested condition.
- `params` (Dict): Dictionary of parameters for parameterized queries.

**Returns:**
- `Tuple[str, Dict]`: A tuple containing the SQL condition string and the updated parameters dictionary.

### `_process_filter`

The `_process_filter` method processes a filter dictionary and converts it into an SQL WHERE clause. It handles both top-level logical operators (`$and`, `$or`) and field-specific conditions.

**Parameters:**
- `filter_dict` (Dict): Filter dictionary with operators.
- `params` (Dict): Dictionary of parameters for parameterized queries.

**Returns:**
- `Tuple[str, Dict]`: A tuple containing the SQL WHERE clause and the parameters dictionary.

### `full_text_search`

The `full_text_search` method performs a full-text search on a specific field in the collection. It constructs and executes a SQL query to search for the specified query in the given field and returns the results.

**Parameters:**
- `field_name` (str): The field name to search in.
- `query` (str): The search query.
- `limit` (int): The maximum number of results to return (default: 30).

**Returns:**
- `List[Dict[str, Any]]`: A list of document dictionaries with scores.

### `get_documents_by_ids`

The `get_documents_by_ids` method retrieves documents from the collection by their IDs. It constructs and executes a SQL query to fetch the documents with the specified IDs and returns them as a dictionary.

**Parameters:**
- `ids` (List[str]): A list of document IDs to retrieve.

**Returns:**
- `Dict[str, Dict[str, Any]]`: A dictionary mapping IDs to document data.

### `search_with_filters`

The `search_with_filters` method performs a search with filters on the collection. It constructs and executes a SQL query based on the provided search query and filter dictionary, and returns the results.

**Parameters:**
- `query` (str): The search query.
- `filter_dict` (Dict): The filter dictionary.
- `limit` (int): The maximum number of results to return (default: 30).

**Returns:**
- `List[Dict[str, Any]]`: A list of document dictionaries.

### `__del__`

The `__del__` method is a destructor that ensures the PostgreSQL connection is closed when the `PGVectorSearch` object is deleted.

## Dependencies Used and Their Descriptions

### `psycopg2`

The `psycopg2` library is used to connect to and interact with the PostgreSQL database. It provides the necessary functions and classes to establish connections, execute queries, and handle results.

### `psycopg2.extras`

The `psycopg2.extras` module provides additional features for `psycopg2`, such as the `RealDictCursor` used to fetch query results as dictionaries.

### `json`

The `json` module is used to handle JSON data, particularly for converting filter values to JSON format for SQL queries.

### `logging`

The `logging` module is used to log errors and other information during the execution of the code. It helps in debugging and monitoring the application's behavior.

### `typing`

The `typing` module provides type hints and type checking for the function parameters and return values, improving code readability and maintainability.

## Functional Flow

The functional flow of the `pgvector_search.py` file involves the following steps:

1. **Initialization:** The `PGVectorSearch` class is initialized with the connection string, collection name, and language for full-text search.
2. **Connection Management:** The `_get_connection` and `_close_connection` methods manage the PostgreSQL connection, ensuring it is established and closed properly.
3. **Filter Processing:** The `_process_filter_condition` and `_process_filter` methods handle the conversion of filter dictionaries into SQL WHERE clauses.
4. **Search Operations:** The `full_text_search`, `get_documents_by_ids`, and `search_with_filters` methods perform various search operations on the collection, constructing and executing SQL queries based on the provided parameters.
5. **Cleanup:** The `__del__` method ensures the PostgreSQL connection is closed when the `PGVectorSearch` object is deleted.

## Endpoints Used/Created

The `pgvector_search.py` file does not explicitly define or call any endpoints. It primarily interacts with the PostgreSQL database to perform search operations.