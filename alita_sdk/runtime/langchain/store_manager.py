import threading
import atexit
import logging
from psycopg import Connection
from langgraph.store.postgres import PostgresStore

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

    def get_store(self, conn_str: str) -> PostgresStore:
        store = self._stores.get(conn_str)
        if store is None:
            logger.info(f"Creating new PostgresStore for connection: {conn_str}")
            conn = Connection.connect(conn_str, autocommit=True, prepare_threshold=0)
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