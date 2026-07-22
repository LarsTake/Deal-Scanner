class DealScannerError(Exception):
    """Base error safe to map to a structured API problem."""


class ProviderError(DealScannerError):
    pass


class ProviderRateLimited(ProviderError):
    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(f"Provider rate limited; retry after {retry_after_seconds:.0f}s")
        self.retry_after_seconds = retry_after_seconds


class LeaseConflict(DealScannerError):
    pass
