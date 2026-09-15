from .minio_storage import MinIoStorage

class StorageFactory:
    def __init__(self,config:dict):
            self.config=config

    def create(self):
        # provider = os.getenv("STORAGE_PROVIDER", "minio").lower()
        provider = self.config.STORAGE_PROVIDER.lower()
        
        if provider == "minio" or provider == "s3":
            return  MinIoStorage(self.config)
        else:
            raise ValueError(f"Unsupported storage provider: {provider}")
                

