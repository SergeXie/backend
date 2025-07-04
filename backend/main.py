import uvicorn
from common.log import log
from core.registrar import register_app
from scheduled_task.backtesting_task import scheduler
from contextlib import asynccontextmanager

app = register_app()


# @app.on_event("startup")
# async def startup_event():
#     print("FastAPI 启动，定时任务调度器启动")
#     scheduler.start()


if __name__ == "__main__":

    log.info("启动")
    uvicorn.run(app, host="0.0.0.0", port=8081)