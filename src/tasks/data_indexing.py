from celery_app import celery_app, get_setup_utils
import logging
import asyncio
from tqdm.auto import tqdm
from controllers import  NLPController
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models import ResponseSignal

logger=logging.getLogger(__name__)


@celery_app.task(bind=True)
def index_data_content(self, project_id:int, do_reset:int):
    return asyncio.run(
        _index_data_content(self,project_id, do_reset)
        )



async def _index_data_content(task_instance,project_id:int, do_reset:int):
    vectordb_client, db_engine= None, None


    try:
        (db_engine, db_client,
        llm_provider_factory,vectordb_provider_factory,storage_provider_factory,
        generation_client,embedding_client,vectordb_client,
        template_parser,
        storage_client)= await get_setup_utils()
        project_model= await ProjectModel.create_instance(
                db_client=db_client,
            )
        
        chunk_model= await ChunkModel.create_instance(
            db_client=db_client,
        )
        project= await project_model.get_project_or_create_one(
            project_id=project_id
        )
        if not project :
            task_instance.update_state(
                state="FAILURE",
                meta={
                    "singal":ResponseSignal.PROJECT_NOT_FOUND.value
                }
            )
            raise Exception(f"No project found for project_id: {project_id}")
            
        nlp_controller=NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser

        )
        has_record=True
        page_no=1
        inserted_item_count=0
        idx=0

        collection_name= nlp_controller.create_collection_name(project_id=project.project_id)
        _ = await vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=embedding_client.embedding_size,
            do_reset= do_reset,
        )
        total_chunks_count= await chunk_model.get_total_chunks_count(project_id=project.project_id)
        pbar= tqdm(total=total_chunks_count, desc="Vector Indexing", position=0)
        while has_record:
            page_chunks= await chunk_model.get_project_chunks(
                project_id=project.project_id,
                page_no=page_no
            )
            if len(page_chunks):
                page_no +=1

            if  not page_chunks or len(page_chunks)==0:
                has_record=False
                break 

            chunks_ids= [c.chunk_id for c in page_chunks]
            idx+= len(page_chunks)
            is_inserted=await nlp_controller.index_into_vector_db(
                project=project,
                chunks=page_chunks,
                chunks_ids=chunks_ids,
            )

            if not is_inserted:
                task_instance.update_state(
                    state="FAILURE",
                    meta={
                        "signal":ResponseSignal.INSERT_INTO_VECTOR_DB_ERROR.value
                    }
                )
                raise Exception(f" cannot insert into VectoDb | project_id: {project_id}")
            pbar.update(len(page_chunks))
            inserted_item_count+= len(page_chunks)

        task_instance.update_state(
            state="SUCCESS",
            meta={
                "signal": ResponseSignal.INSERT_INTO_VECTOR_DB_SUCCESS.value,

            }
            )
        return {
                    "signal": ResponseSignal.INSERT_INTO_VECTOR_DB_SUCCESS.value,
                    "inserted_item_count":inserted_item_count
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