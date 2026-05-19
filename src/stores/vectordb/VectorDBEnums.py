from enum import Enum

class VectorDBEnums(Enum):
    QDRANT="QDRANT"
    PGVECTOR="PGVECTOR"


class DistanceMethodEnum(Enum):
    COSINE="COSINE"
    DOT="DOT"


class PgVectroDistanceMethodEnums(Enum):
    COSINE="vector_cosine_ops"
    DOT="vector_l2_ops"

class PgVectorTableSchemaEnums(Enum):
    ID="id"
    TEXT ="text"
    VECTOR="vector"
    CHUNK_ID="chunk_id"
    METADATA="metadata"
    _PREFIX="pgvector"


class PgVectorIndexTypeEnums(Enum):
    IVFFLAT="ivfflat"
    HNSW="hnsw"