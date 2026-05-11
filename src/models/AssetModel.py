from .BaseDataModel import BaseDataModel
from .db_schemes import Asset
from .enums.DatabaseEnum import DatabaseEnum
from bson import ObjectId
class AssetModel(BaseDataModel):
    def __init__(self, db_client:object):
        super().__init__(db_client)
        self.db_client= db_client


    @classmethod
    async def create_instance(cls,db_client:object):
        instance= cls(db_client)
        await instance.init_collection()
        return instance
    


    async def create_asset(self, asset:Asset):
        result= await self.collection.insert_one(
            asset.model_dump(by_alias=True,exclude_unset=True)
            )
    
        asset.asset_id = result.inserted_id

        return asset

    async def get_all_projects_assets(self, asset_project_id:str, asset_type:str):
        records= await self.collection.find({
            "asset_project_id":ObjectId(asset_project_id) if isinstance(asset_project_id,str) else asset_project_id,
            "asset_type":asset_type 
        }).to_list(length=None)
        return [
            Asset(**record)
            for record in records
        ]
    
    async def get_asset_record(self,asset_project_id:str, asset_name:str):
        record= await self.collection.find_one({
            "asset_project_id":ObjectId(asset_project_id) if isinstance(asset_project_id,str) else asset_project_id,
            "asset_name": asset_name
        })
        if record:
            return Asset(**record)

        return None