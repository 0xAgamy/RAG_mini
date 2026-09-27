from abc import ABC, abstractmethod

from typing import Optional
from fastapi import UploadFile

class BaseStorage(ABC):
    @abstractmethod
    async def upload_file(self,file: UploadFile, object_name:str):
        """Upload file and return it's url"""
        pass

    @abstractmethod
    async def download_file(self, object_name:str, dest_path:str):
        """ download a file to a dest"""
        pass

    @abstractmethod
    async def delete_file(self, object_name:str) ->bool:
        """delete a file from storage"""
        pass

    @abstractmethod
    async def file_exists(self, object_name:str) -> bool:
        """check if a file exist"""
        pass

    @abstractmethod
    async def file_size(self, object_name:str):
        """get the file size"""
        pass

    @abstractmethod
    async def get_file_content(self, object_name: str) -> bytes:
        pass