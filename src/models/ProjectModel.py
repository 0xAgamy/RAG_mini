from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from sqlalchemy.exc import IntegrityError

from sqlalchemy.future import select
from sqlalchemy import func
class ProjectModel(BaseDataModel):
    def __init__(self, db_client:object):
        super().__init__(db_client)

        self.db_client= db_client

    @classmethod
    async def create_instance(cls,db_client:object):
        instance= cls(db_client)
       
        return instance






    async def create_project(self, project:Project):
        async with self.db_client() as session:
            async with session.begin():
                session.add(project)
            await session.commit()
            await session.refresh(project)

        return project



    async def get_project_or_create_one(self,project_id:int):
        stmt= select(Project).where(Project.project_id==project_id)
        async with self.db_client() as session:
            existing= (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        try:
            return await self.create_project(project=Project(project_id=project_id))
        except IntegrityError:
            async with self.db_client() as session:
                existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing is None:
                raise

            return existing

    async def get_all_projects(self,page:int=1, page_size:int=10):
        async with self.db_client() as session:
            async with session.begin():
                total_docs= await session.execute(select(
                    func.count(Project.project_id)

                )).scalar_one() 
                total_pages = -(-total_docs // page_size)  
                
                query= select(Project).order_by(Project.project_id).offset((page -1) * page_size).limit(page_size)
                projects= await session.execute(query).scalars().all()
            
        return projects, total_pages
