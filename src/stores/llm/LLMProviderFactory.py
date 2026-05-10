from .LLMEnums import LLMEnums
from .providers import OpenAIProvider, CoHereProvider
class LLMProviderFactory:
    def __init__(self,config:dict):
        self.config=config
    
    def create(self, provider:str):
        if provider == LLMEnums.OPENAI.value:
            return OpenAIProvider(
                api_key=self.config.OPENAI_API_KEY,
                base_url=self.config.OPENAI_API_URL,
                default_generation_max_output_tokens=self.config.DEFAULT_GENERATION_MAX_OUTPUT_TOKENS,
                default_generation_temperature=self.config.DEFAULT_GENERATION_TEMPERATURE,
                default_input_max_characters=self.config.DEFAULT_INPUT_MAX_CHARACTERS
            )

        if provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key=self.config.COHERE_API_KEY,
                default_generation_max_output_tokens=self.config.DEFAULT_GENERATION_MAX_OUTPUT_TOKENS,
                default_generation_temperature=self.config.DEFAULT_GENERATION_TEMPERATURE,
                default_input_max_characters=self.config.DEFAULT_INPUT_MAX_CHARACTERS
            )


        return None


