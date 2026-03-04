# main_api.py
import sys
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保项目根路径在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api import auth_routes, inventory_routes
from services.inventory_service import start_all_compensate_services
from utils.logger import ContextLogger

logger = ContextLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="库存管理系统 API",
    description="提供库存管理、用户认证、支付补偿等接口",
    version="1.0.0"
)

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_routes.router)
app.include_router(inventory_routes.router)

@app.on_event("startup")
async def startup_event():
    """启动后台补偿服务"""
    logger.info("正在启动库存补偿服务...")
    start_all_compensate_services()
    logger.info("所有补偿服务已启动")

@app.get("/")
async def root():
    return {"message": "库存管理系统 API 已启动", "docs": "/docs"}

if __name__ == "__main__":
    uvicorn.run(
        "main_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # 开发时启用热重载
        log_level="info"
    )