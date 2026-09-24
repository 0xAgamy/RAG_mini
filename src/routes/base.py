from fastapi import FastAPI, APIRouter,Depends
import os

from helpers.config import get_settings,Settings

from time import sleep
import logging

from tasks.mail_service import send_email_reports

logger= logging.getLogger("uvicorn.error")

base_router=APIRouter(
    prefix="/api/v1",
    tags=['api_v1']
)
    
@base_router.get("/")
async def welcome(app_settings:Settings=Depends(get_settings)):
    app_name=app_settings.APP_NAME
    app_version=app_settings.APP_VERSION
    return{
        "app":app_name,
        "version":app_version
    }

@base_router.get("/send_reports")
async def send_reports(app_settings:Settings=Depends(get_settings)):
    task= send_email_reports.delay(
        mail_waits_seconds=3
    )

    return {
        "success": True,
        "task_id": task.id
    }

