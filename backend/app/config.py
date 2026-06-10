from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    db: str = '/app/data/cloudpilot.db'
    secret_key: str = 'change-this-secret-key'
    admin_user: str = 'admin'
    admin_password: str = 'admin123'
    class Config:
        env_prefix = 'CLOUDPILOT_'
settings = Settings()
