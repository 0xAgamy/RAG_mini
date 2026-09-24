from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from helpers.config import get_settings,Settings

from controllers import DataController, ProjectController, ProcessController, NLPController
import os
import aiofiles
from models import ResponseSignal
import uuid
import logging
from .schemes.data import ProcessRequest 
from models.ProjectModel import ProjectModel
from models.db_schemes import DataChunk, Asset
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel

from models.enums.AssetTypeEnum import AssetTeypeEnum
from tasks.file_processing import process_project_file

logger= logging.getLogger("uvicorn.error")
data_router=APIRouter(
    prefix="/api/v1/data",
    tags=['api_v1','data']
)

@data_router.post("/upload/{project_id}")
async def upload_data(request:Request,project_id:int, file:UploadFile,
                    app_settings:Settings=Depends(get_settings)):
    
    project_model= await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project= await project_model.get_project_or_create_one(
        project_id=project_id
    )

    data_controller= DataController()
    is_valid, result_signal= data_controller.validate_uploaded_file(file=file)
    
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal
            }
        )

    file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
    object_name = f"documents/{uuid.uuid4()}.{file_extension}"
    
    file_id=await request.app.storage_client.upload_file(file,object_name)
    file_size= await request.app.storage_client.file_size(object_name)
    
    # store asset in db
    asset_model= await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    asset_resource= Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTeypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=file_size
    )
    asset_record= await asset_model.create_asset(asset_resource)

    return JSONResponse(
            content={
                "signal": ResponseSignal.FILE_UPLOADED_SUCCESS.value,
                "file_id": str(asset_record.asset_id),
                
            }
        )


@data_router.post("/process/{project_id}")
async def process_endpoint(request:Request,project_id:int,process_request:ProcessRequest):
    task= process_project_file.delay(
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset
    )
    return JSONResponse(
        content={
            "singal": "process",
            "task_id": task.id,
        }
    )
