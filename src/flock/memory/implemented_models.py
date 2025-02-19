import numpy as np
import ollama
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from .model import ChatModel, EmbeddingModel
from .memory_manager import ConceptExtractionResponse


class OpenAIEmbeddingModel(EmbeddingModel):
    def __init__(self, api_key, model_name="text-embedding-3-small"):
        self.api_key = api_key
        self.model_name = model_name
        self.embeddings_model = OpenAIEmbeddings(model=model_name, api_key=self.api_key)

        if model_name == "text-embedding-3-small":
            self.dimension = 1536
        else:
            raise ValueError("Unsupported OpenAI embedding model name for specified dimension.")

    def get_embedding(self, text: str) -> np.ndarray:
        embedding = self.embeddings_model.embed_query(text)
        if embedding is None:
            raise ValueError("Failed to generate embedding.")
        return np.array(embedding)

    def initialize_embedding_dimension(self) -> int:
        return self.dimension


class OllamaEmbeddingModel(EmbeddingModel):
    def __init__(self, model_name="mxbai-embed-large"):
        self.model_name = model_name
        self.dimension = self.initialize_embedding_dimension()

    def get_embedding(self, text: str) -> np.ndarray:
        response = ollama.embeddings(model=self.model_name, prompt=text)
        embedding = response.get("embedding")
        if embedding is None:
            raise ValueError("Failed to generate embedding.")
        return np.array(embedding)

    def initialize_embedding_dimension(self) -> int:
        test_text = "Test to determine embedding dimension"
        response = ollama.embeddings(
            model=self.model_name,
            prompt=test_text
        )
        embedding = response.get("embedding")
        if embedding is None:
            raise ValueError("Failed to retrieve embedding for dimension initialization.")
        return len(embedding)


class OpenAIChatModel(ChatModel):
    def __init__(self, api_key, model_name="gpt-3.5-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, api_key=self.api_key)
        self.parser = JsonOutputParser(pydantic_object=ConceptExtractionResponse)
        self.prompt_template = PromptTemplate(
            template=(
                "Extract key concepts from the following text in a concise, context-specific manner. "
                "Include only highly relevant and specific concepts.\n"
                "{format_instructions}\n{text}"
            ),
            input_variables=["text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    def invoke(self, messages: list) -> str:
        response = self.llm.invoke(messages)
        return str(response.content)

    def extract_concepts(self, text: str) -> list[str]:
        chain = self.prompt_template | self.llm | self.parser
        response = chain.invoke({"text": text})
        concepts = response.get("concepts", [])
        print(f"Concepts extracted: {concepts}")
        return concepts


class OllamaChatModel(ChatModel):
    def __init__(self, model_name="llama3.1:8b"):
        self.model_name = model_name
        self.llm = ChatOllama(model=model_name, temperature=0)
        self.parser = JsonOutputParser(pydantic_object=ConceptExtractionResponse)
        self.prompt_template = PromptTemplate(
            template=(
                "Please analyze the following text and provide a list of key concepts that are unique to this content. "
                "Return only the core concepts that best capture the text's meaning.\n"
                "{format_instructions}\n{text}"
            ),
            input_variables=["text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    def invoke(self, messages: list) -> str:
        response = self.llm.invoke(messages)
        return str(response.content)

    def extract_concepts(self, text: str) -> list[str]:
        chain = self.prompt_template | self.llm | self.parser
        response = chain.invoke({"text": text})
        concepts = response.get("concepts", [])
        print(f"Concepts extracted: {concepts}")
        return concepts

class ChatCompletionsModel(ChatModel):
    def __init__(self, api_endpoint: str, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = ChatOpenAI(openai_api_base = api_endpoint, openai_api_key = api_key, model_name = model_name)
        self.parser = JsonOutputParser(pydantic_object=ConceptExtractionResponse)
        self.prompt_template = PromptTemplate(
            template=(
                "Extract key concepts from the following text in a concise, context-specific manner. "
                "Include only the most highly relevant and specific core concepts that best capture the text's meaning. "
                "Return nothing but the JSON string.\n"
                "{format_instructions}\n{text}"
            ),
            input_variables=["text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    def invoke(self, messages: list) -> str:
        response = self.llm.invoke(messages)
        return str(response.content)
    
    def extract_concepts(self, text: str) -> list[str]:
        chain = self.prompt_template | self.llm | self.parser
        response = chain.invoke({"text": text})
        concepts = response.get("concepts", [])
        print(f"Concepts extracted: {concepts}")
        return concepts

class OpenRouterChatModel(ChatCompletionsModel):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_endpoint="https://openrouter.ai/api/v1", api_key=api_key, model_name=model_name)
