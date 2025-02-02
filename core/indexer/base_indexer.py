from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Type, Optional, Tuple
from urllib.parse import urlparse

from .hasher import Hasher, HashLibHasher


class BaseIndexer(ABC):
    """Base class for file indexers."""
    
    # Registry for indexer types
    _indexer_types: Dict[str, Type['BaseIndexer']] = {}
    
    def __init__(self, db_path: str, hasher: Hasher):
        """Initialize indexer.
        
        Args:
            db_path: Path to the index storage
            hasher: Hasher instance to use for file hashing
        """
        self.db_path = db_path
        self._hasher = hasher
        self._db = None
    
    @property
    def hasher(self) -> Hasher:
        """Get current hasher instance."""
        return self._hasher
    
    @classmethod
    def register(cls, scheme: str, indexer_cls: Type['BaseIndexer']) -> None:
        """Register an indexer type for a specific URI scheme.
        
        Args:
            scheme: URI scheme
            indexer_cls: Indexer class to register
        """
        cls._indexer_types[scheme] = indexer_cls
    
    @classmethod
    def parse_uri(cls, uri: str) -> tuple[str, str, str]:
        """Parse URI into scheme, path and hash algorithm.
        
        Args:
            uri: URI for the index storage, format: scheme[+hash_algo]://filename
                e.g. 'dbm+sha256://hash.index' or 'dbm://hash.index'
            
        Returns:
            tuple[str, str, str]: (scheme, filename, hash_algorithm)
            
        Raises:
            ValueError: If URI format is invalid
        """
        try:
            # Split URI into scheme and filename parts
            if "://" not in uri:
                raise ValueError("URI must contain '://'")
                
            scheme_part, filename = uri.split("://", 1)
            if not scheme_part or not filename:
                raise ValueError("Missing scheme or filename")
                
            # Parse scheme and hash algorithm
            scheme_parts = scheme_part.split("+", 1)
            scheme = scheme_parts[0]
            hash_algorithm = scheme_parts[1] if len(scheme_parts) > 1 else "sha256"
            
            return scheme, filename, hash_algorithm
        except Exception as e:
            raise ValueError(f"Invalid URI format: {uri}") from e
    
    @classmethod
    def create(cls, uri: str, work_dir: str) -> 'BaseIndexer':
        """Create an indexer instance based on URI.
        
        Args:
            uri: URI for the index storage, format: scheme[+hash_algo]://filename
                e.g. 'dbm+sha256://hash.index' or 'dbm://hash.index'
            work_dir: Working directory where the index file will be stored
            
        Returns:
            BaseIndexer: An instance of appropriate indexer type
            
        Raises:
            ValueError: If URI scheme is not supported or URI format is invalid
        """
        # Parse URI
        scheme, filename, hash_algorithm = cls.parse_uri(uri)
        
        # Check if scheme is supported
        if scheme not in cls._indexer_types:
            raise ValueError(f"Unsupported URI scheme: {scheme}")
            
        # Check if filename contains path separators
        if any(sep in filename for sep in ['/', '\\']):
            raise ValueError(f"URI should only contain filename without path: {filename}")
            
        # Create full path by joining work_dir and filename
        path = str(Path(work_dir) / filename)
        
        # Create hasher
        hasher = HashLibHasher(hash_algorithm)
        
        # Create indexer instance
        return cls._indexer_types[scheme](path, hasher)
    
    @classmethod
    def cleanup_uri(cls, uri: str) -> None:
        """Clean up any files associated with the given URI.
        
        Args:
            uri: URI string (e.g., 'dbm://./hash.index')
        """
        scheme, path = cls.parse_uri(uri)[:2]
        
        if scheme not in cls._indexer_types:
            raise ValueError(
                f"Unsupported indexer type: {scheme}. "
                f"Supported types: {', '.join(cls._indexer_types.keys())}"
            )
        
        cls._indexer_types[scheme].cleanup(path)
    
    @abstractmethod
    def cleanup(self, path: str) -> None:
        """Clean up any files associated with the given path.
        
        Args:
            path: Path to the index storage
        """
        pass
    
    @abstractmethod
    def open(self) -> None:
        """Open the index storage."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the index storage."""
        pass
    
    @abstractmethod
    def add(self, file_path: str, file_hash: Optional[str] = None) -> str:
        """Add a file to the index.
        
        Args:
            file_path: Path to the file to add
            file_hash: Optional pre-calculated hash value
            
        Returns:
            str: Hash value of the added file
        """
        pass
    
    @abstractmethod
    def remove(self, file_path: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[str]:
        """Remove a file from the index.
        
        Args:
            file_path: Path to the file, optional if file_hash is provided
            file_hash: Hash of the file, optional if file_path is provided
            
        Returns:
            Optional[str]: Hash value of the removed file if it existed, None otherwise
            
        Raises:
            ValueError: If neither file_path nor file_hash is provided
        """
        pass
        
    @abstractmethod
    def add_if_absent(self, file_path: str) -> Tuple[bool, str]:
        """Add a file to the index if it's not already present.
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            Tuple[bool, str]: (True if file was added, False if it already existed, file hash value)
        """
        pass
    
    @abstractmethod
    def get(self, file_path: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[str]:
        """Get relative path by file path or hash.
        
        Args:
            file_path: Path to the file, optional if file_hash is provided
            file_hash: Hash of the file, optional if file_path is provided
            
        Returns:
            str: Relative path if found, None otherwise
            
        Raises:
            ValueError: If neither file_path nor file_hash is provided
        """
        pass
    
    @abstractmethod
    def exists(self, file_path: Optional[str] = None, file_hash: Optional[str] = None) -> bool:
        """Check if a file exists in the index.
        
        Args:
            file_path: Path to the file, optional if file_hash is provided
            file_hash: Hash of the file, optional if file_path is provided
            
        Returns:
            True if exists, False otherwise
            
        Raises:
            ValueError: If neither file_path nor file_hash is provided
        """
        pass
    
    @abstractmethod
    def list(self, n: int = None) -> list[tuple[str, str]]:
        """List items in the index.
        
        Args:
            n: Number of items to return, if None return all items
            
        Returns:
            list[tuple[str, str]]: List of (hash, path) tuples, sorted by path
        """
        pass
    
    def _get_relative_path(self, file_path: str) -> str:
        """Get relative path from file path to index storage directory.
        
        Args:
            file_path: Absolute path to the file
            
        Returns:
            str: Relative path
        """
        return str(Path(file_path).resolve().relative_to(Path(self.db_path).parent.resolve()))
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
