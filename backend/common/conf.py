from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="mysql+aiomysql://cmdb:cmdb123456@192.168.1.126:3306/dql?charset=utf8mb4")
    AI_URL: str = Field(default="http://192.168.1.60:8083/api/ai/myai")

    # Env Redis
    REDIS_HOST: str = Field(default="127.0.0.1")
    REDIS_PORT: int = Field(default=2000)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_DATABASE: int = Field(default=0)

    # FastAPI
    API_V1_STR: str = Field(default='/api/v1')
    TITLE: str = Field(default='FastAPI')
    VERSION: str = Field(default='0.0.1')
    DESCRIPTION: str = Field(default='FastAPI SQLAlchemy MySQL')
    DOCS_URL: str = Field(default=f'/api/v1/docs')
    REDOCS_URL: str = Field(default=f'/api/v1/redocs')
    OPENAPI_URL: str = Field(default=f'/api/v1/openapi')


    # Static Server
    STATIC_FILE: bool = Field(default=True)

    # Uvicorn
    UVICORN_HOST: str = Field(default='127.0.0.1')
    UVICORN_PORT: int = Field(default=9000)
    UVICORN_RELOAD: bool = Field(default=True)

    # DateTime
    DATETIME_TIMEZONE: str = Field(default='Asia/Shanghai')
    DATETIME_FORMAT: str = Field(default='%Y-%m-%d %H:%M:%S')

    # Redis
    REDIS_TIMEOUT: int = Field(default=10)

    # Captcha
    CAPTCHA_EXPIRATION_TIME: int = Field(default=60 * 5)  # 过期时间，单位：秒

    # Log
    LOG_STDOUT_FILENAME: str = Field(default='fsm_access.log')
    LOG_STDERR_FILENAME: str = Field(default='fsm_error.log')

    # 中间件
    MIDDLEWARE_CORS: bool = Field(default=True)
    MIDDLEWARE_GZIP: bool = Field(default=True)
    MIDDLEWARE_ACCESS: bool = Field(default=False)

    # 配置加载规则
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False,  # 区分大小写，通常环境变量推荐全大写
        env_nested_delimiter='__',
        extra='ignore'
    )

settings = Settings()
