class MissingEnvironmentVariable(Exception):
    """
    Missing environment variable.
    That exception raised when some of
    environment variables is not exists.
    """


class EndpointBadResponse(Exception):
    """Response does not meet expecations."""
