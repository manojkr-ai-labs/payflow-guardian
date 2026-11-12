class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def unauthorized(message: str = "Sign in to continue.") -> AppError:
    return AppError("unauthorized", message, 401)


def forbidden(message: str) -> AppError:
    return AppError("forbidden", message, 403)


def not_found(message: str) -> AppError:
    return AppError("not_found", message, 404)


def validation_failed(message: str) -> AppError:
    return AppError("validation_failed", message, 422)


def paypal_failed(message: str) -> AppError:
    return AppError("paypal_failed", message, 502)


def needs_checking(message: str) -> AppError:
    return AppError("needs_checking", message, 409)


def approval_required(message: str) -> AppError:
    return AppError("approval_required", message, 409)


def approval_stale(message: str) -> AppError:
    return AppError("approval_stale", message, 409)
