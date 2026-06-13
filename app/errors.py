from collections.abc import Mapping


class ApplicationError(Exception):
    """Base class for controlled failures that map to API problems."""

    def __init__(
        self,
        detail: str,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context = dict(context or {})

    def add_context(self, **context: object) -> None:
        """Add safe diagnostic fields at a meaningful application boundary."""
        self.context.update(context)


class AuthenticationRequiredError(ApplicationError):
    """Raised when bearer credentials are missing."""


class InvalidCredentialsError(ApplicationError):
    """Raised when supplied bearer credentials are invalid."""


class DatabaseUnavailableError(ApplicationError):
    """Raised when the database dependency is unavailable or unhealthy."""


class IdentityProviderUnavailableError(ApplicationError):
    """Raised when identity-provider signing keys cannot be retrieved safely."""


class FileStorageError(ApplicationError):
    """Raised when file-storage processing fails unexpectedly."""


class InvalidPdfError(FileStorageError):
    """Raised when an uploaded file does not satisfy the PDF contract."""


class FileStorageUnavailableError(FileStorageError):
    """Raised when the storage backend cannot persist a valid upload."""


class UploadTooLargeError(FileStorageError):
    """Raised when uploaded content exceeds the configured limit."""
