from celery_app import celery_app, get_setup_utils
import logging
import asyncio

from controllers import DataController, ProjectController, ProcessController, NLPController
import os
import aiofiles
from models import ResponseSignal
import uuid
import logging

from models.ProjectModel import ProjectModel
from models.db_schemes import DataChunk, Asset
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.enums.AssetTypeEnum import AssetTeypeEnum

logger=logging.getLogger(__name__)
@celery_app.task(bind=True,
                autoretry_for=(Exception,),
    retry_kwargs={"max_retries":3, "countdown":60})
def process_project_file(self,
                        project_id:int,
                        file_id:int,
                        chunk_size,
                        overlap_size,
                        do_reset,
                        ):

    asyncio.run(_process_project_file(
        self,
         project_id,
        file_id,
        chunk_size,
        overlap_size,
        do_reset,
    ))


async def _process_project_file(task_instance,
                        project_id:int,
                        file_id:int,
                        chunk_size,
                        overlap_size,
                        do_reset,
                        ):

    vectordb_client, db_engine= None, None
    try:

        (db_engine, db_client,
        llm_provider_factory,vectordb_provider_factory,storage_provider_factory,
        generation_client,embedding_client,vectordb_client,
        template_parser,
        storage_client
        )= await get_setup_utils()


        project_model= await ProjectModel.create_instance(
            db_client=db_client
        )
        project= await project_model.get_project_or_create_one(
            project_id=project_id
        )
        nlp_controller= NLPController(
            vectordb_client=vectordb_client,
            generation_client= generation_client,
            embedding_client= embedding_client,
            template_parser= template_parser
        )
        process_controller= ProcessController(project_id=project_id)
        asset_model= await AssetModel.create_instance(
                db_client= db_client
            )
        project_file_ids= {}    
        if file_id :
            asset_record= await asset_model.get_asset_record(
                asset_project_id=project.project_id,
                asset_name=file_id
            )
            if asset_record is None:
                task_instance.update_state(
                    state="FAILURE",
                    meta={
                    "signal": ResponseSignal.FILE_ID_ERROR.value 
                    }
                )
                raise Exception(f"No assets for file: {file_id}")
                
                
            project_file_ids={
                asset_record.asset_id: asset_record.asset_name
            }
        else:
            

            project_files=  await asset_model.get_all_projects_assets(asset_project_id=project.project_id,
                                                                    asset_type=AssetTeypeEnum.FILE.value)

            project_file_ids={
                record.asset_id : record.asset_name
                for record in project_files
            }
        
        if len(project_file_ids)== 0:
            task_instance.update_state(
                            state="FAILURE",
                            meta={
                            "singal": ResponseSignal.NO_FILES_ERROR.value

                            }
            )
            raise Exception(f"No files found for project_id: {project.project_id}")
            
        
        chunk_model= await ChunkModel.create_instance(
                db_client=db_client
            )
        

        if do_reset ==1:
                    collection_name= nlp_controller.create_collection_name(project_id=project.project_id)
                    _= await vectordb_client.delete_collection(collection_name=collection_name)
                    _ =await chunk_model.delete_chunks_by_project_id(
                        project_id=project.project_id
                )

        no_records,no_files= 0, 0

        for asset_id,file_id in project_file_ids.items():
            
            file_content=await storage_client.get_file_content(file_id)
            file_content= process_controller.get_file_loader(file_content,file_id)
            if file_content is None:
                logger.error(f"Error while processing file: {file_id}")
                continue
            file_chunks =process_controller.process_file_content(
                file_content=file_content,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )

            if file_chunks is None or len(file_chunks) == 0:

                logger.error(f"No chunks for file_id: {file_id}")
                pass
            file_chunks_records= [
                DataChunk(
                    chunk_text= chunk.page_content,
                    chunk_metadata= chunk.metadata,
                    chunkd_order= i+1,
                    chunk_project_id= project.project_id,
                    chunk_asset_id=asset_id
                )
                for i, chunk in enumerate(file_chunks)
            ]

        
            no_records+= await chunk_model.insert_many_chunks(chunks= file_chunks_records)
            no_files+=1

        task_instance.update_state(
            status="SUCCESS",
            meta={
                "singal": ResponseSignal.PROCESSING_SUCCESS.value,
            }
        )

        return {
                "singal": ResponseSignal.PROCESSING_SUCCESS.value,
                "inserted_chunks": no_records,
                "processed_files":no_files
            
        }
    except Exception as e:
        logger.error(f"Task Faild : {str(e)}")
        raise
    finally:
        try:
            if db_engine:
                await db_engine.dispose()
            if vectordb_client:
                await vectordb_client.disconnect()
        except Exception as e:
                logger.error(f"Task Faild while cleaning : {str(e)}")
                raise
