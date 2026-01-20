"""
Client Registry for Shared API Client Management

This module provides a centralized registry for API clients to avoid
creating duplicate HTTP connections when multiple toolkits connect
to the same service.

Key Features:
- Clients are cached by (service_type, base_url, auth_hash)
- Thread-safe access with locking
- Automatic cleanup of stale connections
- Connection pooling across toolkits

Usage:
    from alita_sdk.tools.client_registry import ClientRegistry

    # Get or create a client
    client = ClientRegistry.get_client(
        service_type="jira",
        base_url="https://jira.company.com",
        auth_config={"token": "..."},
        factory=lambda: Jira(url=url, token=token)
    )

    # Client is shared across all toolkits with same connection params
"""

import hashlib
import logging
import threading
import weakref
from typing import Any, Callable, Dict, Optional, TypeVar
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ClientEntry:
    """Entry in the client registry."""
    client: Any
    service_type: str
    base_url: str
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    reference_count: int = 1

    def touch(self):
        """Update last accessed time and increment reference count."""
        self.last_accessed = datetime.now()
        self.reference_count += 1


class ClientRegistry:
    """
    Centralized registry for sharing API clients across toolkits.

    This prevents resource duplication when multiple toolkits connect
    to the same service (e.g., 3 Jira toolkits for same server).

    Thread-safe singleton implementation.
    """

    _instance: Optional['ClientRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._clients: Dict[str, ClientEntry] = {}
        self._client_lock = threading.RLock()
        self._initialized = True
        logger.info("[ClientRegistry] Initialized")

    @classmethod
    def get_instance(cls) -> 'ClientRegistry':
        """Get the singleton instance."""
        return cls()

    @staticmethod
    def _compute_auth_hash(auth_config: Dict[str, Any]) -> str:
        """
        Compute a hash of authentication config for cache key.

        Handles SecretStr and other sensitive values safely.
        """
        # Normalize auth config for hashing
        normalized = {}
        for key, value in sorted(auth_config.items()):
            if hasattr(value, 'get_secret_value'):
                # Handle SecretStr - use hash of value, not value itself
                normalized[key] = hashlib.sha256(
                    value.get_secret_value().encode()
                ).hexdigest()[:16]
            elif isinstance(value, str):
                normalized[key] = value
            elif value is not None:
                normalized[key] = str(value)

        # Create deterministic hash
        config_str = str(sorted(normalized.items()))
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    @staticmethod
    def _make_cache_key(service_type: str, base_url: str, auth_hash: str) -> str:
        """Create a cache key for a client."""
        # Normalize base_url (remove trailing slash)
        base_url = base_url.rstrip('/')
        return f"{service_type}:{base_url}:{auth_hash}"

    def get_client(
        self,
        service_type: str,
        base_url: str,
        auth_config: Dict[str, Any],
        factory: Callable[[], T],
        force_new: bool = False
    ) -> T:
        """
        Get or create a client for the given service.

        Args:
            service_type: Type of service (e.g., 'jira', 'github', 'confluence')
            base_url: Base URL of the service
            auth_config: Authentication configuration (token, username, etc.)
            factory: Callable that creates a new client if not cached
            force_new: If True, always create a new client (bypass cache)

        Returns:
            The API client (shared or new)
        """
        auth_hash = self._compute_auth_hash(auth_config)
        cache_key = self._make_cache_key(service_type, base_url, auth_hash)

        with self._client_lock:
            if not force_new and cache_key in self._clients:
                entry = self._clients[cache_key]
                entry.touch()
                logger.info(
                    f"[ClientRegistry] Reusing {service_type} client for {base_url} "
                    f"(refs: {entry.reference_count})"
                )
                return entry.client

            # Create new client
            logger.info(f"[ClientRegistry] Creating new {service_type} client for {base_url}")
            try:
                client = factory()
                self._clients[cache_key] = ClientEntry(
                    client=client,
                    service_type=service_type,
                    base_url=base_url
                )
                return client
            except Exception as e:
                logger.error(f"[ClientRegistry] Failed to create {service_type} client: {e}")
                raise

    def release_client(
        self,
        service_type: str,
        base_url: str,
        auth_config: Dict[str, Any]
    ) -> bool:
        """
        Release a reference to a client.

        Decrements reference count. Client is kept for potential reuse.

        Args:
            service_type: Type of service
            base_url: Base URL of the service
            auth_config: Authentication configuration

        Returns:
            True if client was found and released
        """
        auth_hash = self._compute_auth_hash(auth_config)
        cache_key = self._make_cache_key(service_type, base_url, auth_hash)

        with self._client_lock:
            if cache_key in self._clients:
                entry = self._clients[cache_key]
                entry.reference_count = max(0, entry.reference_count - 1)
                logger.debug(
                    f"[ClientRegistry] Released {service_type} client "
                    f"(refs: {entry.reference_count})"
                )
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached clients."""
        with self._client_lock:
            stats = {
                'total_clients': len(self._clients),
                'by_service': {},
                'clients': []
            }

            for key, entry in self._clients.items():
                # Count by service type
                svc = entry.service_type
                stats['by_service'][svc] = stats['by_service'].get(svc, 0) + 1

                # Client details
                stats['clients'].append({
                    'service_type': entry.service_type,
                    'base_url': entry.base_url,
                    'reference_count': entry.reference_count,
                    'created_at': entry.created_at.isoformat(),
                    'last_accessed': entry.last_accessed.isoformat()
                })

            return stats

    def clear(self, service_type: Optional[str] = None):
        """
        Clear cached clients.

        Args:
            service_type: If provided, only clear clients of this type
        """
        with self._client_lock:
            if service_type:
                keys_to_remove = [
                    k for k, v in self._clients.items()
                    if v.service_type == service_type
                ]
                for key in keys_to_remove:
                    del self._clients[key]
                logger.info(f"[ClientRegistry] Cleared {len(keys_to_remove)} {service_type} clients")
            else:
                count = len(self._clients)
                self._clients.clear()
                logger.info(f"[ClientRegistry] Cleared all {count} clients")


# Global singleton instance
_registry = None


def get_client_registry() -> ClientRegistry:
    """Get the global ClientRegistry instance."""
    global _registry
    if _registry is None:
        _registry = ClientRegistry()
    return _registry
