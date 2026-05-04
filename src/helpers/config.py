from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError


class Settings(BaseSettings):
    APP_NAME:str
    APP_VERSION:str

    FILE_ALLOWED_TYPES:list
    FILE_MAX_SIZE:int
    FILE_DEFAULT_CHUNK_SIZE:int

    MONGODB_URL:str
    MONGODB_DATABASE:str


    GENERATION_BACKEND:str
    EMBEDDING_BACKEND:str

    OPENAI_API_KEY:str= None
    OPENAI_API_URL:str= None
    COHERE_API_KEY:str= None

    GENERATION_MODEL_ID:str= None
    EMBEDING_MODEL_ID:str= None
    EMBEDDING_MODEL_SIZE:int= None


    DEFAULT_INPUT_MAX_CHARACTERS:int= None
    DEFAULT_GENERATION_MAX_OUTPUT_TOKENS:int= None
    DEFAULT_GENERATION_TEMPERATURE:float= None

    model_config = SettingsConfigDict(env_file="src/.env")

def get_settings():
    try:
        return Settings()
    except ValidationError as e:
        print("Missing required environment variables")
        raise e