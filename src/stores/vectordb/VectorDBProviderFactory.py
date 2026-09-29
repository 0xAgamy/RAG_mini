from .providers import QdrantDBProvider, PgVectorProvider
from .VectorDBEnums import VectorDBEnums
from controllers.BaseController import BaseController
class VectorDBProviderFactory:
    def __init__(self,config,db_client):
        self.config= config
        self.base_controller=BaseController()
        self.db_client= db_client

    def create(self,provider:str):
        if provider == VectorDBEnums.QDRANT.value:
            return QdrantDBProvider(
                db_client=self.config.VECTR_DB_PATH,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
            )
        if provider == VectorDBEnums.PGVECTOR.value:
            return PgVectorProvider(
                db_client=self.db_client,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threshold=self.config.VECTOR_DB_PGVEC_INDEX_THRESHOLD
            )

        
        raise ValueError(
            f"Unsupported vector db provider {provider!r}; "
            f"expected one of {[e.value for e in VectorDBEnums]}"
        )

