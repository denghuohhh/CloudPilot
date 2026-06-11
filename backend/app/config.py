from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    db: str = '/app/data/cloudpilot.db'
    secret_key: str = 'dev-only-change-me'
    admin_user: str = 'admin'
    admin_password: str = 'change-me-before-use'
    class Config:
        env_prefix = 'CLOUDPILOT_'
settings = Settings()
