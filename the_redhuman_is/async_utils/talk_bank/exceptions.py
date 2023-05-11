from typing import (
    List,
    Optional,
)


class TalkBankExceptionError(Exception):
    """Talk bank exception."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.errors = errors

    def __str__(self) -> str:
        message = self.message.strip('.')
        errors = ''
        if self.errors:
            errors = '; '.join(self.errors)
        return '{0}. {1}'.format(
            message,
            errors,
        ).strip()

    def __repr__(self) -> str:
        return 'TalkBankException("{0}", status_code={1}, errors={2})'.format(
            self.message,
            self.status_code,
            self.errors,
        )


class InternalServerError(TalkBankExceptionError):
    pass


class AccessDeniedError(TalkBankExceptionError):
    pass


class ForbiddenError(TalkBankExceptionError):
    pass


class BadRequestError(TalkBankExceptionError):
    pass


class ClientWithSuchPhoneAlreadyExistsError(TalkBankExceptionError):
    pass


class ClientAlreadyExistsError(TalkBankExceptionError):
    pass

