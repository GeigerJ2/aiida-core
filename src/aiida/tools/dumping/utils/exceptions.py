class DumpError(Exception):
    """Base class for dump-related exceptions"""

class PathValidationError(DumpError):
    """Raised when a path fails validation"""

class DirectoryExistsError(PathValidationError):
    """Raised when target directory already exists"""

class SafeguardFileError(DumpError):
    """Raised when safeguard file operations fail"""

class MissingSafeguardError(SafeguardFileError):
    """Raised when safeguard file is missing during validation"""

class NodeValidationError(DumpError):
    """Base class for node validation errors"""

class UnsealedNodeError(NodeValidationError):
    """Raised when attempting to dump an unsealed node"""

class GroupValidationError(DumpError):
    """Raised when group validation fails"""

class LoggingError(DumpError):
    """Raised when logging operations fail"""

class LogDeserializationError(LoggingError):
    """Raised when log file cannot be deserialized"""

class MappingValidationError(DumpError):
    """Raised when group-node mapping validation fails"""

# class NodeDumpError(DumpError):
#     """Raised when group-node mapping validation fails"""

# class GroupUpdateError(DumpError):
#     """Raised when group-node mapping validation fails"""
