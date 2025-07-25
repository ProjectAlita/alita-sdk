import threading
import atexit
import logging
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

class StoreManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._stores = {}
        return cls._instance

    def _parse_connection_string(self, conn_str: str) -> dict:
        """
        Parse the connection string from SQLAlchemy style to args dict.
        """
        if conn_str.startswith("postgresql+psycopg://"):
            url = conn_str[len("postgresql+psycopg://"):]

        parsed = urlparse(f"//{url}")

        return {
            "user": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
            "host": parsed.hostname,
            "port": parsed.port,
            "dbname": parsed.path.lstrip("/") if parsed.path else None
        }

    def get_store(self, conn_str: str):
        from psycopg import Connection
        from langgraph.store.postgres import PostgresStore
        
        store = self._stores.get(conn_str)
        if store is None:
            logger.info(f"Creating new PostgresStore for connection: {conn_str}")
            conn_params = self._parse_connection_string(conn_str)
            conn_params.update({'autocommit': True, 'prepare_threshold': 0})
            conn = Connection.connect(**conn_params)
            store = PostgresStore(conn)
            store.setup()
            self._stores[conn_str] = store
        return store

    def shutdown(self) -> None:
        logger.info("Shutting down StoreManager and closing all stores")
        for store in list(self._stores.values()):
            try:
                conn = getattr(store, 'conn', None)
                if conn:
                    conn.close()
            except Exception:
                pass
        self._stores.clear()

_store_manager = StoreManager()
atexit.register(_store_manager.shutdown)

def get_manager() -> StoreManager:
    return _store_manager