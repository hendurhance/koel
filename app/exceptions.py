from fastapi import HTTPException

class NotFoundException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)

class ValidationException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class ScrapingException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)

class RateLimitException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=429, detail=detail)

class InternalServerErrorException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)