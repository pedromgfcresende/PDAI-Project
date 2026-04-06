from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "ai_trends"
    db_user: str = "trends"
    db_password: str = "changeme"

    # LLM API keys
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    google_ai_api_key: str = ""

    # GitHub
    github_token: str = ""

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "PDAI-Project"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
