from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lab Robot Management System"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your_super_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "postgresql://robot_user:robot_password@localhost:5432/labrobot"

    class Config:
        env_file = ".env"

settings = Settings()
