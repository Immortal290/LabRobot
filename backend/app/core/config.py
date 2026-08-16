from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lab Robot Management System"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your_super_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./labrobot.db"

    # ── Gmail API (Web Application OAuth2) ────────────────────────────────────
    # From Google Cloud Console → Credentials → your Web Client → Copy values
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    # Get this ONCE via: https://developers.google.com/oauthplayground
    GMAIL_REFRESH_TOKEN: str = ""
    # The Gmail address used to authorize (the Lab Buddy sender account)
    GMAIL_SENDER_ADDRESS: str = ""
    GMAIL_SENDER_NAME: str = "Lab Buddy"

    class Config:
        env_file = ".env"

settings = Settings()
