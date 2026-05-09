from fastapi import FastAPI
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient
from src.helpers.config import get_settings
from src.routes import base,data, nlp
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.stores.llm.templates.template_parser import TemplateParser





async def startup_span(app:FastAPI):
    settings=get_settings()
    app.mongo_conn=AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client= app.mongo_conn[settings.MONGODB_DATABASE]

    llm_provider_factory=LLMProviderFactory(settings)
    vectordb_provider_factory=VectorDBProviderFactory(settings)
    app.generation_client=llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    app.embedding_client= llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDING_MODEL_ID,
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)
    
    app.vectordb_client=vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )
    app.vectordb_client.connect()
    app.template_parser=TemplateParser(
        language=settings.DEFAULT_LANGUAGE
    )


async def shutdown_span(app:FastAPI):
    app.mongo_conn.close()
    app.vectordb_client.disconnect()






@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_span(app)
    yield
    await shutdown_span(app)

app=FastAPI(lifespan=lifespan)
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
