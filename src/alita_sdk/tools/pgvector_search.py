from typing import List, Tuple, Dict, Any, Optional
from logging import getLogger
import psycopg2
import json

logger = getLogger(__name__)

class PGVectorSearch:
    """Helper class for working directly with PGVector for full-text search"""
    
    def __init__(self, connection_string: str, collection_name: str, language: str = 'english'):
        """Initialize with PostgreSQL connection string and collection name
        
        Args:
            connection_string: PostgreSQL connection string
            collection_name: Name of the collection in PostgreSQL langchain_pg_collection table
            language: Language for PostgreSQL full-text search (e.g., 'english', 'spanish', 'german')
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.collection_id = self._get_collection_id()
        self.embedding_table = "langchain_pg_embedding"  # Default embedding table name
        self.language = language
        
    def _get_connection(self):
        """Get a PostgreSQL connection"""
        return psycopg2.connect(self.connection_string)
    
    def _get_collection_id(self):
        """Get the collection_id for the given collection name from langchain_pg_collection"""
        conn = None
        collection_id = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Query to get collection_id from name
            sql = "SELECT uuid FROM langchain_pg_collection WHERE name = %s"
            cursor.execute(sql, (self.collection_name,))
            
            result = cursor.fetchone()
            if result:
                collection_id = result[0]
                logger.info(f"Found collection ID {collection_id} for collection {self.collection_name}")
            else:
                logger.error(f"Collection {self.collection_name} not found in langchain_pg_collection")
                
        except Exception as e:
            logger.error(f"Error getting collection ID: {str(e)}")
        finally:
            if conn:
                conn.close()
                
        return collection_id
    
    def full_text_search(self, field_name: str, query: str, limit: int = 50) -> List[Dict]:
        """Perform full-text search on a specific metadata field
        
        Args:
            field_name: Field name in cmetadata to search
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of dictionaries with doc_id, metadata, and text_score
        """
        if not self.collection_id:
            logger.error("Cannot perform search - collection ID not found")
            return []
            
        results = []
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Updated PostgreSQL full-text search query to use the configured language
            sql = f"""
            SELECT uuid, cmetadata, 
                   ts_rank_cd(to_tsvector('{self.language}', cmetadata->'{field_name}'), 
                             plainto_tsquery('{self.language}', %s)) AS rank
            FROM {self.embedding_table}
            WHERE collection_id = %s
              AND cmetadata->'{field_name}' IS NOT NULL
              AND to_tsvector('{self.language}', cmetadata->'{field_name}') @@ plainto_tsquery('{self.language}', %s)
            ORDER BY rank DESC
            LIMIT %s
            """
            
            cursor.execute(sql, (query, self.collection_id, query, limit))
            
            for row in cursor.fetchall():
                doc_id, metadata_json, text_score = row
                results.append({
                    'id': doc_id,
                    'metadata': json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json,
                    'text_score': float(text_score)
                })
                
        except Exception as e:
            logger.error(f"Full-text search error: {str(e)}")
        finally:
            if conn:
                conn.close()
                
        return results
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> Dict[str, Dict]:
        """Retrieve documents by their UUIDs
        
        Args:
            doc_ids: List of document UUIDs to retrieve
            
        Returns:
            Dictionary mapping document IDs to document data
        """
        if not self.collection_id:
            logger.error("Cannot retrieve documents - collection ID not found")
            return {}
            
        results = {}
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Updated query to match the table structure
            placeholders = ', '.join(['%s'] * len(doc_ids))
            sql = f"""
            SELECT uuid, embedding, document, cmetadata, custom_id
            FROM {self.embedding_table}
            WHERE collection_id = %s AND uuid IN ({placeholders})
            """
            
            # Add collection_id as the first parameter
            params = [self.collection_id] + doc_ids
            cursor.execute(sql, params)
            
            for row in cursor.fetchall():
                uuid, embedding, document, cmetadata, custom_id = row
                results[uuid] = {
                    'id': uuid,
                    'document': document,
                    'cmetadata': json.loads(cmetadata) if isinstance(cmetadata, str) else cmetadata,
                    'embedding': embedding,
                    'custom_id': custom_id
                }
                
        except Exception as e:
            logger.error(f"Error retrieving documents by IDs: {str(e)}")
        finally:
            if conn:
                conn.close()
                
        return results
