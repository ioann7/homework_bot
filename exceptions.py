class BaseStateDeviation(Exception):
    """Base exception class state deviation."""


class SendMessageError(BaseStateDeviation):
    """Telegram message not sent."""


class MissingNotRequiredKey(BaseStateDeviation):
    """Missing not required key in Response."""


class EndpointBadResponse(Exception):
    """Response does not meet expecations."""
