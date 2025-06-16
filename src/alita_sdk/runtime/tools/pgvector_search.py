import psycopg2
import psycopg2.extras
import json
from logging import getLogger
from typing import List, Dict, Any, Optional, Union, Tuple

logger = getLogger(__name__)

class PGVectorSearch:
    """Helper class for PostgreSQL vector search operations"""
    
    def __init__(self, connection_string: str, collection_name: str, language: str = 'english'):
        """
        Initialize PGVector search helper
        
        Args:
            connection_string: PostgreSQL connection string
            collection_name: Name of the collection/table to search
            language: Language for full-text search (default: 'english')
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.language = language
        self._conn = None
    
    def _get_connection(self):
        """Get a PostgreSQL connection"""
        if not self._conn or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_string)
        return self._conn
    
    def _close_connection(self):
        """Close the PostgreSQL connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None
    
    def _process_filter_condition(self, key: str, value: Any, params: Dict) -> Tuple[str, Dict]:
        """
        Process a single filter condition to SQL
        
        Args:
            key: The field name or operator
            value: The filter value or nested condition
            params: Dictionary of parameters for parameterized queries
        
        Returns:
            Tuple of (SQL condition string, updated parameters dict)
        """
        if key.startswith("$"):
            # Operator
            if key == "$eq":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"= %({param_name})s", params
            elif key == "$ne":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"!= %({param_name})s", params
            elif key == "$lt":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"< %({param_name})s", params
            elif key == "$lte":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"<= %({param_name})s", params
            elif key == "$gt":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"> %({param_name})s", params
            elif key == "$gte":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f">= %({param_name})s", params
            elif key == "$in":
                if not isinstance(value, (list, tuple)):
                    value = [value]
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"= ANY(%({param_name})s)", params
            elif key == "$nin":
                if not isinstance(value, (list, tuple)):
                    value = [value]
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"!= ALL(%({param_name})s)", params
            elif key == "$between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError("$between requires a list or tuple with exactly 2 elements")
                param_name1 = f"p{len(params) + 1}"
                param_name2 = f"p{len(params) + 2}"
                params[param_name1] = value[0]
                params[param_name2] = value[1]
                return f"BETWEEN %({param_name1})s AND %({param_name2})s", params
            elif key == "$exists":
                if value:
                    return "IS NOT NULL", params
                else:
                    return "IS NULL", params
            elif key == "$like":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"LIKE %({param_name})s", params
            elif key == "$ilike":
                param_name = f"p{len(params) + 1}"
                params[param_name] = value
                return f"ILIKE %({param_name})s", params
            elif key == "$and":
                if not isinstance(value, list):
                    raise ValueError("$and requires a list of conditions")
                conditions = []
                for condition in value:
                    condition_sql, params = self._process_filter(condition, params)
                    conditions.append(f"({condition_sql})")
                return " AND ".join(conditions), params
            elif key == "$or":
                if not isinstance(value, list):
                    raise ValueError("$or requires a list of conditions")
                conditions = []
                for condition in value:
                    condition_sql, params = self._process_filter(condition, params)
                    conditions.append(f"({condition_sql})")
                return " OR ".join(conditions), params
            else:
                raise ValueError(f"Unsupported operator: {key}")
        else:
            # Field name
            if isinstance(value, dict):
                # Process operators within the field
                conditions = []
                for op, op_value in value.items():
                    op_sql, params = self._process_filter_condition(op, op_value, params)
                    conditions.append(f"(cmetadata->'{key}' {op_sql})")
                return " AND ".join(conditions), params
            else:
                # Direct equality
                param_name = f"p{len(params) + 1}"
                params[param_name] = json.dumps(value)
                return f"cmetadata->'{key}' = %({param_name})s::jsonb", params
    
    def _process_filter(self, filter_dict: Dict, params: Dict = None) -> Tuple[str, Dict]:
        """
        Process filter dictionary into SQL WHERE clause
        
        Args:
            filter_dict: Filter dictionary with operators
            params: Dictionary of parameters for parameterized queries
        
        Returns:
            Tuple of (SQL WHERE clause, parameters dict)
        """
        if params is None:
            params = {}
        
        if not filter_dict:
            return "TRUE", params
        
        # Check if this is a top-level logical operator
        if len(filter_dict) == 1 and list(filter_dict.keys())[0] in ["$and", "$or"]:
            return self._process_filter_condition(list(filter_dict.keys())[0], list(filter_dict.values())[0], params)
        
        # Otherwise, treat top level as implicit $and
        conditions = []
        for field, value in filter_dict.items():
            condition, params = self._process_filter_condition(field, value, params)
            conditions.append(condition)
        
        return " AND ".join(conditions), params
    
    def full_text_search(self, field_name: str, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Perform a full-text search on a specific field
        
        Args:
            field_name: Field name to search in
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of document dictionaries with scores
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Extract the field from JSON and perform text search
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
    
    def get_documents_by_ids(self, ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve documents by IDs
        
        Args:
            ids: List of document IDs to retrieve
            
        Returns:
            Dictionary mapping IDs to document data
        """
        if not ids:
            return {}
            
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            placeholders = ", ".join(["%s" for _ in ids])
            sql = f"""
                SELECT 
                    id, document, cmetadata
                FROM 
                    {self.collection_name}
                WHERE 
                    id IN ({placeholders})
            """
            
            cursor.execute(sql, ids)
            results = cursor.fetchall()
            
            # Build dictionary mapping IDs to document data
            documents = {}
            for row in results:
                doc_id = row['id']
                documents[doc_id] = dict(row)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            conn.rollback()
            return {}
        finally:
            cursor.close()
    
    def search_with_filters(self, query: str, filter_dict: Dict = None, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Perform a search with filters
        
        Args:
            query: Search query
            filter_dict: Filter dictionary
            limit: Maximum number of results
            
        Returns:
            List of document dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            params = {"query": query, "limit": limit}
            
            where_clause = "TRUE"
            if filter_dict:
                where_clause, filter_params = self._process_filter(filter_dict)
                params.update(filter_params)
            
            sql = f"""
                SELECT 
                    id, document, cmetadata
                FROM 
                    {self.collection_name}
                WHERE 
                    {where_clause}
                LIMIT 
                    %(limit)s
            """
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error searching with filters: {str(e)}")
            conn.rollback()
            return []
        finally:
            cursor.close()

    def __del__(self):
        """Cleanup connection when object is deleted"""
        self._close_connection()
