from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (DistanceMethodEnum, PgVectorIndexTypeEnums,
                              PgVectorTableSchemaEnums, PgVectroDistanceMethodEnums)

from typing import List
from src.models.db_schemes.ragdb.schemes.datachunk import RetrievedDocument
from sqlalchemy import text as sql_text
import json
import logging

class PgVectorProvider(VectorDBInterface):
    def __init__(self, db_client, default_vector_size:int=786,
                 distance_method:str=None,
                 index_threshold:int=100):
        self.db_client = db_client
        self.default_vector_size = default_vector_size
        if distance_method == DistanceMethodEnum.COSINE.value:
            distance_method= PgVectroDistanceMethodEnums.COSINE.value
        elif distance_method== DistanceMethodEnum.DOT.value:
            distance_method== PgVectroDistanceMethodEnums.DOT.value

        self.distance_method = distance_method 
        self.index_threshold=index_threshold
        self.pgvector_table_prefix = PgVectorTableSchemaEnums._PREFIX.value
        self.logger = logging.getLogger("uvicorn")
        self.default_index_name= lambda collection_name: f"{collection_name}_vector_idx" 

    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(
                    "CREATE EXTENSION IF NOT EXISTS vector"
                ))

            await session.commit()
    async def disconnect(self):
        pass

    async def is_collection_exist(self,collection_name:str)->bool:
        record = None
        async with self.db_client() as session:
            async with session.begin():
                list_tbl= sql_text(f"SELECT * FROM pg_tables WHERE tablename= :collection_name")
                results= await session.execute(list_tbl, {"collection_name":collection_name} )
                record= results.scalar_one_or_none()

        return record
    
    async def list_all_collections(self) ->List:
        records= []
        async with self.db_client() as session:
            async with session.begin():
                list_tbls= sql_text("SELLECT * FROM pg_tables WHERE tablename LIKE :prefix")

                results= await session.execute(list_tbls, {"prefix": self.pgvector_table_prefix})
                return results.scalars().all()
        return records
    
    async def get_collection_info(self, collection_name:str)->dict:
        async with self.db_client() as session:
            async with session.begin():
                table_info_sql= sql_text(
                    f"""SELECT schemaname, tablename, tableowner, tablespace, hasindexes
                    FROM  pg_tables
                    WHERE tablename= :collection_name
                    """
                )
                count_sql= sql_text(f"""SELECT COUNT(*) FROM {collection_name}""")
                records_info= await session.execute(table_info_sql, {"collection_name":collection_name})
                records_count= await session.execute(count_sql)
                table_data= records_info.fetchone()
                if not table_data:
                    return None
                
                return {
                    "table_info": {
                        "schmename":table_data[0],
                        "tablename":table_data[1],
                        "tableowner":table_data[2],
                        "tablespace":table_data[3],
                        "hasindexes":table_data[4],

                    },
                    "records_count": records_count.scalar_one()
                }


    async def delete_collection(self,collection_name:str):
        async with self.db_client() as session:
            async with session.begin():
                drop_sql= sql_text(f"""DROP TABLE IF EXISTS {collection_name}""")
                await session.execute(drop_sql)
                await session.commit()
            
        return True

    async def create_collection(self, collection_name:str,
                          embedding_size:int,
                          do_reset:bool=False):
        if do_reset:
            _=await self.delete_collection(collection_name=collection_name)
        is_collection_exist= await self.is_collection_exist(collection_name=collection_name) 

        if not is_collection_exist:
            self.logger.info(f"Create collection: {collection_name}")
            async with self.db_client() as session:
                async with session.begin():
                    create_sql=sql_text(
                        f"""
                    CREATE TABLE {collection_name} (
                        {PgVectorTableSchemaEnums.ID.value} BIGSERIAL PRIMARY KEY,

                        {PgVectorTableSchemaEnums.TEXT.value} TEXT,

                        {PgVectorTableSchemaEnums.VECTOR.value}
                        VECTOR({embedding_size}),

                        {PgVectorTableSchemaEnums.METADATA.value}
                        JSONB DEFAULT '{{}}',

                        {PgVectorTableSchemaEnums.CHUNK_ID.value}
                        INTEGER,

                        FOREIGN KEY (
                            {PgVectorTableSchemaEnums.CHUNK_ID.value}
                        )
                        REFERENCES chunks(chunk_id)
                    )
                    """
                    )
                    await session.execute(create_sql)
                    # await session.commit()
                return True
            
        return False
    ##

    async def is_index_existed(self,collection_name:str):
        index_name= self.default_index_name(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                check_sql= sql_text(
                    f"""
                    SELECT 1
                    FROM pg_indexes
                    WHERE tablename =:collection_name
                    AND indexname= :index_name
                    """
                )
                results= await session.execute(check_sql,
                                                        {"collection_name":collection_name,
                                                            "index_name":index_name})
                
                return bool(results.scalar_one_or_none())
                
    async def create_vector_index(self,
                                   collection_name:str,
                                   index_type:str=PgVectorIndexTypeEnums.HNSW.value):
        is_index_existed= await self.is_index_existed(collection_name)    
        if is_index_existed:
            return False
        
        async with self.db_client() as session:
            async with session.begin():
                count_sql= sql_text(f"SELECT COUNT(*) FROM {collection_name}")
                result= await session.execute(count_sql)
                record_counts= result.scalar_one()

                if record_counts < self.index_threshold:
                    return False
                self.logger.info(f"Start: creating vector index for collection : {collection_name}")
                index_name= self.default_index_name(collection_name)
                create_idx_sql=sql_text(
                    f"""
                    CREATE INDEX  {index_name} ON {collection_name} 
                    USING {index_type} ({PgVectorTableSchemaEnums.VECTOR.value} {self.distance_method})
                    """
                )
                await session.execute(create_idx_sql)

                self.logger.info(f"End: created vector index for collection : {collection_name}")

    async def reset_vector_index(self, collection_name:str,
                                 index_type:str=PgVectorIndexTypeEnums.HNSW.value)->bool:
        
        index_name=self.default_index_name(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                drop_sql= sql_text(f"DROP INDEX IF EXISTS {index_name}")
                await session.execute(drop_sql)

        return await self.create_vector_index(collection_name,index_type)    




    ##

    async def insert_one(self, collection_name:str,
                   text:str, vector:List,
                   metadata:dict=None,
                   record_id:str=None):
        is_collection_exist= await self.is_collection_exist(collection_name=collection_name)
        if not is_collection_exist:
            self.logger.error(f"Can not insert new record to non-existed collection: {collection_name}")
            return False
        
        if not record_id:
            self.logger.error(f"Can not insert new record without chunk_id: {collection_name}")
            return False
        async with self.db_client() as session:
                async with session.begin():
                    insert_sql= sql_text(f'INSERT INTO {collection_name}'
                                         f'({PgVectorTableSchemaEnums.TEXT.value}, {PgVectorTableSchemaEnums.VECTOR.value},{PgVectorTableSchemaEnums.METADATA.value},{PgVectorTableSchemaEnums.CHUNK_ID.value})'
                                         'VALUES (:text, :vector, :metadata, :chunk_id)'
                                         )
                    meta_json= json.dumps(metadata) if metadata is not None else "{}"
                    await session.execute(insert_sql,{
                        "text": text,
                        "vector":"[" +  ",".join([ str(v) for v in vector])  +"]" ,
                        "metadata": meta_json,
                        "chunk_id": record_id
                    })
                    await session.commit()
        await self.create_vector_index(collection_name=collection_name)


        return True

    async def insert_many(self, collection_name:str,
                                texts:List, vectors:List,
                                metadata:List=None,
                                record_id:List=None,
                                batch_size:int=50):
        is_collection_exist= await self.is_collection_exist(collection_name=collection_name)
        if not is_collection_exist:
            self.logger.error(f"Can not insert new records to not existing table: {collection_name}")
            return False
    
        if len(vectors) != len(record_id):
            self.logger.error(f"Invalid data items for collections :{collection_name} ")
            return False
        if not metadata or len(metadata)==0:
            metadata= [None] * len(texts) 
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0 , len(texts), batch_size):
                    batch_texts= texts[i:i+batch_size]
                    batch_vectors= vectors[i:i+batch_size]
                    batch_metadata= metadata[i:i+batch_size]
                    batch_records_ids= record_id[i:i+batch_size]

                    values= []
                    for _text , _vector, _metadata, _records_id in zip(batch_texts,batch_vectors,batch_metadata,batch_records_ids):
                        
                        meta_json= json.dumps(_metadata,ensure_ascii=False) if _metadata is not None else "{}"
                        values.append({
                            "text": _text,
                            "vector":"[" +  ",".join([ str(v) for v in _vector])  +"]" ,
                            "metadata": meta_json,
                            "chunk_id": _records_id
                        })
                    batch_insert_sql= sql_text(f'INSERT INTO {collection_name}'
                                         f'({PgVectorTableSchemaEnums.TEXT.value}, {PgVectorTableSchemaEnums.VECTOR.value},{PgVectorTableSchemaEnums.METADATA.value},{PgVectorTableSchemaEnums.CHUNK_ID.value})'
                                         ' VALUES (:text, :vector, :metadata, :chunk_id)'
                                         )    

                    await session.execute(batch_insert_sql, values) 
            await self.create_vector_index(collection_name=collection_name)
        return True

    async def search_by_vector(self,collection_name:str,vector:list,limit:int=5):
        is_collection_exist= await self.is_collection_exist(collection_name=collection_name)
        if not is_collection_exist:
            self.logger.error(f"Can not Search in non-existed collection: {collection_name}")
            return False
        
        vector ="[" +  ",".join([ str(v) for v in vector])  +"]"    
        async with self.db_client() as session:
                async with session.begin():
                    search_sql= sql_text(
                        f'SELECT {PgVectorTableSchemaEnums.TEXT.value} as text , 1- ({PgVectorTableSchemaEnums.VECTOR.value} <=> :vector) as score'

                          f' FROM {collection_name}'
                          f' ORDER BY score DESC '
                          f'LIMIT {limit}'
                    )
                    result= await session.execute(search_sql, {"vector":vector})
                    records= result.fetchall()
                    return [
                        RetrievedDocument(
                            text= rec.text,
                            score= rec.score
                        )

                        for rec in records
                    ]
