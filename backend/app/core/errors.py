class ServiceError(Exception):
    """A user-facing failure raised by the service layer; main.py turns it into an HTTP response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
