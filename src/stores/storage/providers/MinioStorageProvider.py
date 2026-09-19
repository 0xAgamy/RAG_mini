import os
import asyncio
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile
from stores.storage.base import BaseStorage

class MinIoStorage(BaseStorage):
    def __init__(self, config):
        self.config= config
        super().__init__()
        self.client= Minio(
            self.config.MINIO_ENDPOINT,
            access_key= self.config.MINIO_ROOT_USER,
            secret_key= self.config.MINIO_ROOT_PASSWORD,
            secure=False
        )
        self.bucket_name= self.config.MINIO_BUCKET_NAME
        

    def _enshure_bucket_exist(self):
        if len(self.client.list_buckets()) == 0 :
            self.client.make_bucket(self.bucket_name)


        # if not self.client.bucket_exists(self.bucket_name):
        #     self.client.make_bucket(self.bucket_name)

    async def upload_file(self,file: UploadFile, object_name:str):
        self._enshure_bucket_exist()

        def _upload():
            file.file.seek(0)
            self.client.put_object(
                self.bucket_name,
                object_name,
                file.file,
                length=-1,
                part_size= 10 * 1024 * 1024, # 10mb for the chunk
                content_type=file.content_type or "application/octet-stream"
            )

            return object_name
        return await asyncio.to_thread(_upload)


    async def download_file(self, object_name: str, dest_path: str) -> str:
        def _download():
            self.client.fget_object(self.bucket_name, object_name, dest_path)
            return dest_path
        return await asyncio.to_thread(_download)

    async def delete_file(self, object_name: str) -> bool:
        def _delete():
            try:
                self.client.remove_object(self.bucket_name, object_name)
                return True
            except S3Error:
                return False
        return await asyncio.to_thread(_delete)

    async def file_exists(self, object_name: str) -> bool:
        def _check():
            try:
                self.client.stat_object(self.bucket_name, object_name)
                return True
            except S3Error:
                return False
        return await asyncio.to_thread(_check)


    async def file_size(self, object_name:str):
            def _check():
                    result=self.client.stat_object(self.bucket_name, object_name)
                    return result.size /  1_000_000
            return await asyncio.to_thread(_check)

    async def get_file_content(self, object_name: str) -> bytes:
        def _get():
            response = self.client.get_object(
                self.bucket_name,
                object_name
            )

            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_get)



