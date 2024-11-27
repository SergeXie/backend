import uvicorn
from common.log import log
from core.registrar import register_app

app = register_app()

if __name__ == "__main__":
    log.info("启动")
    uvicorn.run(app, host="0.0.0.0", port=8081)