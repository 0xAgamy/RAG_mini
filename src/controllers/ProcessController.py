from .BaseController import BaseController
from .ProjectController import ProjectController

from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import ProcessingEnum
import os
from typing import List
from dataclasses import dataclass

@dataclass
class Document:
    page_content:str
    metadata: dict

class ProcessController(BaseController):
    def __init__(self,project_id:str):
        super().__init__()  
        self.project_id= project_id
        self.project_path= ProjectController().get_project_path(project_id=project_id)


    def get_file_extension(self, file_id:str):
        return os.path.splitext(file_id)[-1]
    

    def get_file_loader(self,file_id:str):
        file_ext= self.get_file_extension(file_id=file_id)
        file_path= os.path.join(
            self.project_path,
            file_id
        )
        if not os.path.exists(file_path):
            return None
        if file_ext== ProcessingEnum.TXT.value:
            return TextLoader(file_path,encoding='utf-8')
        
        if file_ext== ProcessingEnum.PDF.value:
            return PyMuPDFLoader(file_path)

        return None
    def get_file_content(self,file_id:str):
        loader= self.get_file_loader(file_id=file_id)
        if loader:
            return loader.load()
        return None
    
    def process_file_content(self,file_content:list,file_id,
                              chunk_size:int=100,
                                overlap_size:int=20):
        text_splitter=RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function= len,        
        )
        
        file_content_texts= [
            rec.page_content
            for rec in file_content
        ]
        file_content_metadata=[
            rec.metadata
            for rec in file_content
        ]
        chunks= self.process_simpler_splitter(
            texts=file_content_texts,
            metadatas=file_content_metadata,
            chunk_size=chunk_size,
        )

        # chunks= text_splitter.create_documents(
        #     file_content_texts,
        #     metadatas=file_content_metadata
        # )

        return chunks


    def process_simpler_splitter(self,
                                 texts:List[str],metadatas:List[dict],chunk_size:int,
                                 splitter_tage:str="\n"):
        full_text= " ".join(texts)

        lines= [doc.strip() for doc in full_text.split(splitter_tage) if len(doc.strip()) > 1]

        chunks= []
        current_chunks= ""

        for line in lines:
            current_chunks += line+ splitter_tage
            if len(current_chunks) >= chunk_size:
                chunks.append(Document(
                    page_content=current_chunks.strip(),
                    metadata= {}
                ))

                current_chunks= ""
            
        if len(current_chunks) >0:
                chunks.append(Document(
                    page_content=current_chunks.strip(),
                    metadata= {}
                ))

        return chunks