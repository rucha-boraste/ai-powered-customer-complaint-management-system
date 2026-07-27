from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    GROQ_API_KEY: str
    GROQ_MODEL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_BUCKET: str
    
    model_config = SettingsConfigDict(
        env_file = "backend/.env",
        extra = "ignore"
    )
    
Config = Settings()
#print(f"{Config.DATABASE_URL}")