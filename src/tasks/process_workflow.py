from celery_app import celery_app, get_setup_utils
import logging
import asyncio
from celery import chain
from tasks.file_processing import process_project_file
from tasks.data_indexing import _index_data_content





@celery_app.task(bind=True)
def push_after_process_task(self,prev_task_result):
    project_id= prev_task_result.get("project_id")
    do_reset= prev_task_result.get("do_reset")

    task_result= asyncio.run(
        _index_data_content(self,project_id=project_id,do_reset=do_reset)
    )

    return{
        "project_id":project_id,
        "do_reset":do_reset,
        "task_results": task_result 
    }





@celery_app.task(bind=True)
def process_workflow(self,
                    project_id:int, file_id:int,
                    chunk_size:int, overlap_size:int, do_reset:int):

    workflow= chain(
        process_project_file.s(project_id=project_id,
                            file_id=file_id,chunk_size=chunk_size,
                            overlap_size=overlap_size,
                            do_reset=do_reset),

            
        push_after_process_task.s(),

    )
    result= workflow.apply_async()

    return{
        "signal": "WORKFLOW_STARTED",
        "workflow_id": result.id,
        "tasks":["process_project_file","index_data_content"]
    }