from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnum
import logging
from qdrant_client import QdrantClient, models
from typing import List
from models.db_schemes.ragdb.schemes.datachunk import RetrievedDocument
import asyncio
class QdrantDBProvider(VectorDBInterface):
    def __init__(self,db_client:str,default_vector_size:int,
                distance_method:str=None,
                index_threshold:int=100):
        super().__init__()
        self.client=None
        self.db_client= db_client
        self.default_vector_size= default_vector_size
        self.distance_method=None

        if distance_method == DistanceMethodEnum.COSINE.value:
            self.distance_method= models.Distance.COSINE.value
        else:
            self.distance_method= models.Distance.DOT.value
    
        self.logger= logging.getLogger("uvicorn")



    async def connect(self):
        self.client= QdrantClient(url=self.db_client)
    

    async def disconnect(self):
        self.client=None

    async def is_collection_exist(self,collection_name:str)->bool:
        return self.client.collection_exists(collection_name=collection_name)
    
    async def list_all_collections(self)->List:
        return self.client.get_collections()
    
    async def get_collection_info(self, collection_name:str)->dict:
        return self.client.get_collection(collection_name=collection_name)
    

    async def delete_collection(self,collection_name:str):
        if await self.is_collection_exist(collection_name):
            return self.client.delete_collection(collection_name=collection_name)
        


    async def create_collection(self, collection_name:str,
                          embedding_size:int,
                          do_reset:bool=False):
        
        if do_reset:
            await self.delete_collection(collection_name)
        
        if not await self.is_collection_exist(collection_name):
            self.logger.info(f"Creating new Qdrant collection: {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method)
                 )

            
            return True
        
        self.logger.info(f"Cannot Create a  new Qdrant collection: {collection_name}")
        
        return False 



    async def insert_one(self, collection_name:str,
                text:str, vector:List,
                metadata:dict=None,
                record_id:str=None):

        
        return await self.insert_many(
            collection_name=collection_name,
            texts=[text],
            vectors=[vector],
            metadata=[metadata],
            record_id=[record_id],
        )
        
    async def insert_many(self, collection_name:str,
                texts:List, vectors:List,
                metadata:List=None,
                record_id:List=None,
                batch_size:int=50):

        if not await self.is_collection_exist(collection_name):
            self.logger.error(
                "Cannot insert into non-existent collection: %s", collection_name
            )
            return False
        if not (len(texts) == len(vectors) == len(record_id or [])):
            self.logger.error(
                "Mismatched insert payload for %s: texts=%d vectors=%d ids=%d",
                collection_name,
                len(texts),
                len(vectors),
                len(record_id or []),
            )
            return False

        metadata= metadata if metadata is not None else [{} for _ in texts]
        record_id= record_id if record_id is not None else list(range(len(texts)))

        for start in range(0,len(texts), batch_size):
            end= start + batch_size
            points=[
                models.PointStruct(
                    id=rid,
                    vector=vec,
                    payload={"text":txt,"metadata":meta},
                )
                for rid, txt, vec, meta in zip(
                    record_id[start:end], texts[start:end],
                    vectors[start:end], metadata[start:end],
                )
            ]

            try:
                await asyncio.to_thread(
                    self.client.upsert,
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
            except Exception as e:
                self.logger.error(
                    "Error upserting batch starting at %d into %s: %s",
                    start, collection_name, e
                )
                return False
        return True


    async def search_by_vector(self,collection_name:str,vector:list,limit:int=5):
   


        results= self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            
        )
        if not results :
            return None
        return [    
            RetrievedDocument(**{
                "score": point.score,
                "text": point.payload['text']
            })
            for point in results.points
        ]
        

