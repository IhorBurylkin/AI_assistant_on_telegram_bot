# errors.py
class ApplicationError(Exception):
    """Базовый класс всех внутренних ошибок."""

class OpenAIServiceError(ApplicationError):
    """Ошибка, возникшая при обращении к OpenAI API.

    Args:
        status_code: HTTP-статус (int)
        code:        внутренний код OpenAI (str | None)
        message:     человекочитаемое описание
        original:    исходное исключение SDK
    """
    def __init__(self, status_code: int, code: str | None,
                 message: str, original: Exception):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.__cause__ = original          # для traceback-цепочки
