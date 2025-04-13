from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus


class Config(BaseSettings):
    API_VERSION: str = Field(default="0.1.0", env="API_VERSION")
    API_TITLE: str = Field(default="Koel Exchange Rate API", env="API_TITLE")

    DB_CONNECTION: str = Field(default="postgresql", env="DB_CONNECTION")
    DB_HOST: str = Field(default="localhost", env="DB_HOST")
    DB_PORT: int = Field(default=5432, env="DB_PORT")
    DB_USER: str = Field(default="postgres", env="DB_USER")
    DB_PASSWORD: str = Field(default="password", env="DB_PASSWORD")
    DB_NAME: str = Field(default="koel", env="DB_NAME")

    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0", env="CELERY_BROKER_URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND"
    )

    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: str = Field(default="", env="REDIS_PASSWORD")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @field_validator("DB_CONNECTION")
    def validate_db_connection(cls, v):
        supported = ["postgresql", "mysql", "sqlite"]
        if v not in supported:
            raise ValueError(
                f"Unsupported DB_CONNECTION: {v}. Supported connections are {supported}."
            )
        return v

    @property
    def db_url(self) -> str:
        encoded_password = quote_plus(self.DB_PASSWORD)
        if self.DB_CONNECTION == "postgresql":
            return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif self.DB_CONNECTION == "mysql":
            return f"mysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif self.DB_CONNECTION == "sqlite":
            return f"sqlite:///{self.DB_NAME}"
        else:
            raise ValueError(f"Unsupported DB_CONNECTION: {self.DB_CONNECTION}")

    @property
    def api_title(self) -> str:
        return self.API_TITLE

    @property
    def api_version(self) -> str:
        return self.API_VERSION


config = Config()
