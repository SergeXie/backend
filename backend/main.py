import sys
import uvicorn
from common.log import log
from core.registrar import register_app
from scheduled_task.backtesting_task import scheduler


app = register_app()

RUN_CRON = "--with-cron" in sys.argv


@app.on_event("startup")
async def startup_event():
    if RUN_CRON:
        log.info("FastAPI 启动，定时任务调度器启动")
        scheduler.start()
    else:
        log.info("本实例不启动定时任务")


if __name__ == "__main__":

    log.info("启动")
    # uvicorn.run(app, host="0.0.0.0", port=8082, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8082)

