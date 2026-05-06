from enum import Enum

class VectorDBEnums(Enum):
    QDRANT="QDRANT"


class DistanceMethodEnum(Enum):
    COSINE="COSINE"
    DOT="DOT"