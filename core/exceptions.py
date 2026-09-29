class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "application_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class AuthenticationError(AppError):
    def __init__(self, message: str = "No fue posible autenticar la solicitud."):
        super().__init__(message, 401, "authentication_failed")


class AuthorizationError(AppError):
    def __init__(self, message: str = "No tiene permiso para realizar esta acción."):
        super().__init__(message, 403, "forbidden")


class ConflictError(AppError):
    def __init__(self, message: str = "El registro fue modificado por otro usuario."):
        super().__init__(message, 409, "conflict")


class NotFoundError(AppError):
    def __init__(self, message: str = "El recurso solicitado no existe."):
        super().__init__(message, 404, "not_found")
