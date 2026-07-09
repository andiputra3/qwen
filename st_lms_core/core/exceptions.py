"""
ST-LMS Custom Exceptions. Structured error hierarchy.
All exceptions inherit from STLMSBaseError for unified handling.
"""


class STLMSBaseError(Exception):
    """Base exception for all ST-LMS errors."""
    pass


class DataValidationError(STLMSBaseError):
    """Raised when kline or OI data fails integrity checks."""
    pass


class PipelineWarmupError(STLMSBaseError):
    """Raised when pipeline is accessed before warmup completion."""
    pass


class ConfigurationError(STLMSBaseError):
    """Raised when config is invalid or missing required fields."""
    pass


class ExecutionError(STLMSBaseError):
    """Raised when order execution fails (virtual or live)."""
    pass


class RiverPersistenceError(STLMSBaseError):
    """Raised when River state save/load fails."""
    pass
