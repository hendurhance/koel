from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel

DataT = TypeVar('DataT')

class ApiResponse(BaseModel, Generic[DataT]):
    success: bool
    data: DataT
    message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

def success_response(data: DataT, message: Optional[str] = None) -> ApiResponse[DataT]:
    return ApiResponse(success=True, data=data, message=message)

def error_response(message: str, data: Optional[Any] = None) -> ApiResponse[Any]:
    return ApiResponse(success=False, data=data, message=message)