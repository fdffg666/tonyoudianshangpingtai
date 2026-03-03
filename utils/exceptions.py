# utils/exceptions.py
class BaseInventoryException(Exception):
    """库存系统基础异常类"""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class BusinessException(BaseInventoryException):
    """业务异常（如库存不足、SKU不存在等，用户可感知）"""
    def __init__(self, message: str):
        super().__init__(message, code=400)


class SystemException(BaseInventoryException):
    """系统异常（如数据库错误、Redis错误等，内部错误，不暴露给用户）"""
    def __init__(self, message: str = "系统异常，请稍后重试"):
        super().__init__(message, code=500)