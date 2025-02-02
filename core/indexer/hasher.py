from abc import ABC, abstractmethod
import hashlib
from typing import Dict, Type, Any

class Hasher(ABC):
    """Base class for file hashers."""
    
    @abstractmethod
    def calculate(self, file_path: str) -> str:
        """Calculate hash for the given file.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            str: Hexadecimal hash value
        """
        pass


class HashLibHasher(Hasher):
    """Hasher implementation using hashlib."""
    
    ALGORITHMS: Dict[str, Type[Any]] = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256,
        'sha512': hashlib.sha512
    }
    
    def __init__(self, algorithm: str = 'sha256'):
        """Initialize hasher with specified algorithm.
        
        Args:
            algorithm: Hash algorithm to use, default is 'sha256'.
                      Supported values: 'md5', 'sha1', 'sha256', 'sha512'
                      
        Raises:
            ValueError: If algorithm is not supported
        """
        if algorithm not in self.ALGORITHMS:
            raise ValueError(
                f"Unsupported hash algorithm: {algorithm}. "
                f"Supported algorithms: {', '.join(self.ALGORITHMS.keys())}"
            )
        self.algorithm = algorithm
        
    def calculate(self, file_path: str) -> str:
        """Calculate hash for the given file.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            str: Hexadecimal hash value
        """
        hash_obj = self.ALGORITHMS[self.algorithm]()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                hash_obj.update(byte_block)
        return hash_obj.hexdigest()
