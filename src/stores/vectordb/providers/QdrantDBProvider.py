from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnum
import logging
from qdrant_client import QdrantClient, models
from typing import List
class QdrantDBProvider(VectorDBInterface):
    def __init__(self,db_path:str,distance_method:str):
        super().__init__()
        self.client=None
        self.db_path= db_path
        self.distance_method=None

        if distance_method == DistanceMethodEnum.COSINE.value:
            self.distance_method= models.Distance.COSINE
        elif distance_method== DistanceMethodEnum.DOT.value:
            self.distance_method= models.Distance.DOT

        self.logger= logging.getLogger(__name__)



    def connect(self):
        self.client= QdrantClient(path=self.db_path)
    

    def disconnect(self):
        self.client=None

    def is_collection_exist(self,collection_name:str)->bool:
        return self.client.collection_exists(collection_name=collection_name)
    
    def list_all_collections(self)->List:
        return self.client.get_collections()
    
    def get_collection_info(self, collection_name:str)->dict:
        return self.client.get_collection(collection_name=collection_name)
    

    def delete_collection(self,collection_name:str):
        if self.is_collection_exist(collection_name):
            return self.client.delete_collection(collection_name=collection_name)
        


    def create_collection(self, collection_name:str,
                          embedding_size:int,
                          do_reset:bool=False):
        
        if do_reset:
            _ =self.delete_collection(collection_name)
        
        if not self.is_collection_exist(collection_name):
            _ =self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method)
                 )
            return True
        
        return False 



    def insert_one(self, collection_name:str,
                   text:str, vector:List,
                   metadata:dict=None,
                   record_id:str=None):
        if not self.is_collection_exist(collection_name):
            self.logger.error("Can't insert new record to non-existed collection{collection_name}")
            return False
        
        try:
            _ =self.client.upload_collection(
                collection_name=collection_name,
                vectors=vector,
                payload={
                    "text":text,
                    "metadata":metadata
                }

            )
        except Exception as e:
            self.logger.error("Error while insert: {e}")
            return False
        return True
        
    def insert_many(self, collection_name:str,
                   texts:List, vectors:List,
                   metadata:List=None,
                   record_id:List=None,
                   batch_size:int=50):
        if metadata is None:
            metadata= metadata[None] * len(texts)

        if record_id is None:
            record_id=record_id[None] * len(texts)


        for i in range(0,len(texts), batch_size):
            batch_end= i + batch_size

            batch_text= texts[i:batch_end]
            batch_vectors= vectors[i:batch_end]
            batch_metadata= metadata[i:batch_end]

            batch_record={}
            for x in range(len(batch_text)):
                batch_record= {
                    "vector":batch_vectors[x],
                    "payload":{
                        "text":batch_text[x],
                        "metadata": batch_metadata[x]
                    }
                }

            try:
                _ = self.client.upload_collection(
                    collection_name=collection_name,
                    vectors=batch_record["vector"].value,
                    payload=batch_record["payload"].value

                )
            except Exception as e:
                self.logger.error("Error while inserting batch: {e}")
                False
        return True

    def search_by_vector(self,collection_name:str,vector:list,limit:int=5):
        self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit
        )

        

