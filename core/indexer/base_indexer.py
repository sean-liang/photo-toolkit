from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Type, Tuple
from urllib.parse import urlparse

from .hasher import Hasher


class BaseIndexer(ABC):
    """Base class for all indexers."""
    
    # Registry for indexer types
    _indexer_types: Dict[str, Type['BaseIndexer']] = {}
    
    def __init__(self, db_path: str, hasher: Hasher):
        """Initialize indexer.
        
        Args:
            db_path: Path to the index storage
            hasher: Hasher instance to use for file hashing
        """
        self.db_path = db_path
        self.hasher = hasher
        self._db = None
    
    @classmethod
    def register(cls, scheme: str, indexer_cls: Type['BaseIndexer']) -> None:
        """Register an indexer type for a specific URI scheme.
        
        Args:
            scheme: URI scheme (e.g., 'dbm')
            indexer_cls: Indexer class to register
        """
        cls._indexer_types[scheme] = indexer_cls
    
    @classmethod
    def parse_uri(cls, uri: str) -> Tuple[str, str]:
        """Parse URI into scheme and path.
        
        Args:
            uri: URI string (e.g., 'dbm://./hash.index')
            
        Returns:
            tuple: (scheme, path)
            
        Raises:
            ValueError: If URI format is invalid
        """
        try:
            parsed = urlparse(uri)
            if not parsed.scheme:
                raise ValueError("URI must have a scheme")
            
            # Convert path to absolute path
            path = parsed.netloc + parsed.path
            if path.startswith('//'):
                path = path[2:]  # Remove leading //
            if not path:
                raise ValueError("URI must have a path")
                
            return parsed.scheme, path
        except Exception as e:
            raise ValueError(f"Invalid URI format: {uri}") from e
    
    @classmethod
    def create(cls, uri: str, hasher: Hasher) -> 'BaseIndexer':
        """Create an indexer instance based on URI.
        
        Args:
            uri: URI string (e.g., 'dbm://./hash.index')
            hasher: Hasher instance to use
            
        Returns:
            BaseIndexer: An instance of appropriate indexer type
            
        Raises:
            ValueError: If URI scheme is not supported or URI format is invalid
        """
        scheme, path = cls.parse_uri(uri)
        
        if scheme not in cls._indexer_types:
            raise ValueError(
                f"Unsupported indexer type: {scheme}. "
                f"Supported types: {', '.join(cls._indexer_types.keys())}"
            )
        
        # Convert path to absolute path if it's relative
        if not Path(path).is_absolute():
            path = str(Path(path).resolve())
        
        # Create indexer instance
        return cls._indexer_types[scheme](path, hasher)
    
    @classmethod
    def cleanup_uri(cls, uri: str) -> None:
        """Clean up any files associated with the given URI.
        
        Args:
            uri: URI string (e.g., 'dbm://./hash.index')
        """
        scheme, path = cls.parse_uri(uri)
        
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
    def add(self, file_path: str) -> str:
        """Add a file to the index.
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            str: Hash value of the added file
        """
        pass
    
    @abstractmethod
    def remove(self, file_path: str) -> Optional[str]:
        """Remove a file from the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Optional[str]: Hash value of the removed file if it existed, None otherwise
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
    def get(self, file_path: str) -> Optional[str]:
        """Get relative path by file path.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Relative path if found, None otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if a file exists in the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if exists, False otherwise
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
