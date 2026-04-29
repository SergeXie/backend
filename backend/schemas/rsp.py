from typing import Optional

from pydantic import BaseModel, Field


class ErrorModel(BaseModel):
    """定义一个错误信息模型"""
    status_code: int = Field(400, title="状态码", ge=400, le=499, description="HTTP 4xx 错误响应状态码")
    message: Optional[str] = Field(None, title="错误信息", description="描述性错误信息")


class ResponseSuccess(BaseModel):
    code: int = 200
    message: str = "Success"
