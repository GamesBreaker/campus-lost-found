class EmbeddingError(Exception):
    """A user-facing embedding failure that should be returned as JSON."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
