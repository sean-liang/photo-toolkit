import dbm
import os
from pathlib import Path
from typing import Optional, Tuple

from .base_indexer import BaseIndexer
from .hasher import Hasher


class DBMIndexer(BaseIndexer):
    """An indexer implementation using DBM as backend storage."""
    
    def __init__(self, db_path: str, hasher: Hasher):
        """Initialize DBM indexer.
        
        Args:
            db_path: Path to the DBM database file
            hasher: Hasher instance
        """
        super().__init__(db_path, hasher)
        self._db = None
        # Get the parent directory of the database file as the base directory
        self._base_dir = str(Path(db_path).parent)
        
    def open(self) -> None:
        """Open the DBM database."""
        # Create parent directory if not exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = dbm.open(self.db_path, 'c')
        
    def close(self) -> None:
        """Close the DBM database."""
        if self._db is not None:
            self._db.close()
            self._db = None
            
    def _add_with_hash(self, file_path: str, file_hash: str) -> None:
        """Add a file to the index with its hash.
        
        Args:
            file_path: Path to the file to add
            file_hash: Hash of the file
        """
        relative_path = self._get_relative_path(file_path)
        self._db[file_hash] = relative_path.encode('utf-8')
        
    def add(self, file_path: str) -> str:
        """Add a file to the index.
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            str: Hash value of the added file
        """
        if self._db is None:
            raise RuntimeError("Database not opened")
        
        file_hash = self.hasher.calculate(file_path)
        self._add_with_hash(file_path, file_hash)
        return file_hash
            
    def get(self, file_path: str) -> Optional[str]:
        """Get relative path by file path.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Relative path if found, None otherwise
        """
        if self._db is None:
            raise RuntimeError("Database not opened")
            
        file_hash = self.hasher.calculate(file_path)
        try:
            value = self._db[file_hash]
            return value.decode('utf-8')
        except KeyError:
            return None
            
    def exists(self, file_path: str) -> bool:
        """Check if a file exists in the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if exists, False otherwise
        """
        if self._db is None:
            raise RuntimeError("Database not opened")
            
        file_hash = self.hasher.calculate(file_path)
        return file_hash in self._db
        
    def remove(self, file_path: str) -> Optional[str]:
        """Remove a file from the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Optional[str]: Hash value of the removed file if it existed, None otherwise
        """
        if self._db is None:
            raise RuntimeError("Database not opened")
            
        file_hash = self.hasher.calculate(file_path)
        try:
            del self._db[file_hash]
            return file_hash
        except KeyError:
            return None
            
    def add_if_absent(self, file_path: str) -> Tuple[bool, str]:
        """Add a file to the index if it's not already present.
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            Tuple[bool, str]: (True if file was added, False if it already existed, file hash value)
        """
        if self._db is None:
            raise RuntimeError("Database not opened")
            
        file_hash = self.hasher.calculate(file_path)
        if file_hash in self._db:
            return False, file_hash
            
        self._add_with_hash(file_path, file_hash)
        return True, file_hash

    @classmethod
    def cleanup(cls, path: str) -> None:
        """Clean up any files associated with the given path.
        
        Args:
            path: Path to the DBM database file
        """
        try:
            os.remove(path)
            os.remove(path + '.db')  # dbm may create additional files
        except OSError:
            pass  # Ignore errors if files don't exist

    def _get_relative_path(self, file_path: str) -> str:
        """Get relative path from file path.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Relative path
        """
        return str(Path(file_path).relative_to(self._base_dir))


# Register DBMIndexer with 'dbm' scheme
BaseIndexer.register('dbm', DBMIndexer)
