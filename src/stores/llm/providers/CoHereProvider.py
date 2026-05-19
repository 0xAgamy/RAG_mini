from ..LLMInterface import LLMInterface
from ..LLMEnums import CoHereEnums, DocumentTypeEnum
import cohere
import logging
from typing import Union, List
import asyncio
from time import sleep

class CoHereProvider(LLMInterface):
    def __init__(self, api_key:str,
                 default_input_max_characters:int=1000,
                 default_generation_max_output_tokens:int=1000,
                 default_generation_temperature:float=0.1):
        super().__init__()
        self.api_key=api_key
        self.default_input_max_characters=default_input_max_characters
        self.default_generation_max_output_tokens=default_generation_max_output_tokens
        self.default_generation_temperature=default_generation_temperature

        self.generation_model_id=None

        self.embedding_model_id=None
        self.embedding_size=None
        self.enums=CoHereEnums

        self.client=cohere.ClientV2(api_key=self.api_key)
        self.logger= logging.getLogger(__name__)
    
    def set_generation_model(self, model_id:str):
        self.generation_model_id=model_id
    
    def set_embedding_model(self, model_id:str,embedding_size):
        self.embedding_model_id=model_id
        self.embedding_size=embedding_size

    def process_text(self, text:str):
        return text[:self.default_input_max_characters].strip()
    
    def construct_prompt(self, prompt:str, role:str):
        return {
            "role":role,
            "content":self.process_text(prompt)
        }
    
    def generate_text(self, prompt:str,
                    chat_history:list=[],
                    max_output_tokens:int=None,
                    temperature:float=None):
        if not self.client:
            self.logger.error("Generation model for CoHere was not set")
            return None
        if not self.generation_model_id:
            self.logger.error("Generation model for CoHere was not set")

        max_output_tokens= max_output_tokens if max_output_tokens is not None else self.default_generation_max_output_tokens
        temperature=temperature if temperature is not None else self.default_generation_temperature 

        chat_history.append(
           self.construct_prompt(prompt,role=CoHereEnums.USER.value)
        )
        response=self.client.chat(
            model=self.generation_model_id,
            messages=chat_history,
            temperature=temperature,
            max_tokens=max_output_tokens
        )
        # print(res.message.content[0].text)
        if not response or not response.message:
            self.logger.error("Error while generating text with CoHere")
        
        return response.message.content[0].text
            

    def embed_text(self, text:Union[str,List[str]], document_type:str=None):
        
        if not self.client:
            self.logger.error("Embedding Model for CoHere was not set")
            return None
        if isinstance(text,str):
            text = [text]
        if not self.embedding_model_id:
            self.logger.error("Embedding Model for CoHere was not set")
            return None
        
        input_type= CoHereEnums.DOCUMENT.value
        if document_type == DocumentTypeEnum.QUERY.value:
            input_type= CoHereEnums.QUERY.value
        
        res= self.client.embed(
            model=self.embedding_model_id,
            texts=[self.process_text(t)  for t in text ],
            input_type=input_type,
            embedding_types=['float'],
        )
        sleep(20)

        if not res or not res.embeddings or not res.embeddings.float:
            self.logger.error("Error While embedding text with CoHere")
            return None

        return [f for f in res.embeddings.float]
        # return res.embeddings.float[0]
