#!/usr/bin/env python3
"""
Model integration layer for iagent.

Provides LLM-agnostic interfaces for different model providers.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a chat message in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    name: Optional[str] = None


@dataclass
class ModelResponse:
    """Response from a language model."""
    content: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class Model(ABC):
    """Abstract base class for all language model implementations."""
    
    def __init__(self, model_id: str, **kwargs):
        self.model_id = model_id
        self.kwargs = kwargs
    
    @abstractmethod
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response from the model."""
        pass


class OpenAIModel(Model):
    """OpenAI API model implementation."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install openai")
    
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                **{**self.kwargs, **kwargs}
            )
            
            return ModelResponse(
                content=response.choices[0].message.content,
                usage=response.usage.model_dump() if response.usage else None,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                stream=True,
                **{**self.kwargs, **kwargs}
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI API streaming error: {e}")
            raise


class LiteLLMModel(Model):
    """LiteLLM model implementation for 100+ providers."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.api_key = api_key
        
        try:
            import litellm
            self.litellm = litellm
        except ImportError:
            raise ImportError("litellm package is required. Install with: pip install litellm")
    
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response using LiteLLM."""
        try:
            response = self.litellm.completion(
                model=self.model_id,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                api_key=self.api_key,
                **{**self.kwargs, **kwargs}
            )
            
            return ModelResponse(
                content=response.choices[0].message.content,
                usage=response.usage,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"LiteLLM error: {e}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response using LiteLLM."""
        try:
            response = self.litellm.completion(
                model=self.model_id,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                api_key=self.api_key,
                stream=True,
                **{**self.kwargs, **kwargs}
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LiteLLM streaming error: {e}")
            raise


class OllamaModel(Model):
    """Ollama model implementation for local models."""
    
    def __init__(self, model_id: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("requests package is required. Install with: pip install requests")
    
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response using Ollama API."""
        try:
            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                if msg.role == "system":
                    # Ollama doesn't have system messages, prepend to first user message
                    if ollama_messages and ollama_messages[-1]["role"] == "user":
                        ollama_messages[-1]["content"] = f"System: {msg.content}\n\nUser: {ollama_messages[-1]['content']}"
                    else:
                        # If no user message yet, create one with system content
                        ollama_messages.append({"role": "user", "content": f"System: {msg.content}"})
                else:
                    ollama_messages.append({"role": msg.role, "content": msg.content})
            
            response = self.requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_id,
                    "messages": ollama_messages,
                    "stream": False,
                    **{**self.kwargs, **kwargs}
                }
            )
            response.raise_for_status()
            
            result = response.json()
            
            return ModelResponse(
                content=result["message"]["content"],
                usage=result.get("usage"),
                finish_reason=result.get("done", True)
            )
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response using Ollama API."""
        try:
            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                if msg.role == "system":
                    # Ollama doesn't have system messages, prepend to first user message
                    if ollama_messages and ollama_messages[-1]["role"] == "user":
                        ollama_messages[-1]["content"] = f"System: {msg.content}\n\nUser: {ollama_messages[-1]['content']}"
                    else:
                        # If no user message yet, create one with system content
                        ollama_messages.append({"role": "user", "content": f"System: {msg.content}"})
                else:
                    ollama_messages.append({"role": msg.role, "content": msg.content})
            
            response = self.requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_id,
                    "messages": ollama_messages,
                    "stream": True,
                    **{**self.kwargs, **kwargs}
                },
                stream=True
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    if "message" in chunk and chunk["message"]["content"]:
                        yield chunk["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama API streaming error: {e}")
            raise


class HuggingFaceModel(Model):
    """Hugging Face model implementation."""
    
    def __init__(self, model_id: str, token: Optional[str] = None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.token = token or os.getenv("HF_TOKEN")
        
        try:
            from huggingface_hub import InferenceClient
            self.client = InferenceClient(model=model_id, token=self.token)
        except ImportError:
            raise ImportError("huggingface_hub package is required. Install with: pip install huggingface_hub")
    
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response using Hugging Face Inference API."""
        try:
            # Convert messages to text format
            text = self._messages_to_text(messages)
            
            response = self.client.text_generation(
                text,
                **{**self.kwargs, **kwargs}
            )
            
            return ModelResponse(
                content=response,
                usage=None,
                finish_reason=None
            )
        except Exception as e:
            logger.error(f"Hugging Face API error: {e}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response using Hugging Face Inference API."""
        try:
            text = self._messages_to_text(messages)
            
            response = self.client.text_generation(
                text,
                stream=True,
                **{**self.kwargs, **kwargs}
            )
            
            for chunk in response:
                if chunk.token.text:
                    yield chunk.token.text
        except Exception as e:
            logger.error(f"Hugging Face streaming error: {e}")
            raise
    
    def _messages_to_text(self, messages: List[ChatMessage]) -> str:
        """Convert chat messages to text format."""
        text = ""
        for msg in messages:
            if msg.role == "system":
                text += f"System: {msg.content}\n"
            elif msg.role == "user":
                text += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                text += f"Assistant: {msg.content}\n"
        return text


class BedrockModel(Model):
    """AWS Bedrock model implementation."""
    
    def __init__(self, model_id: str, region: Optional[str] = None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        try:
            import boto3
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.region
            )
        except ImportError:
            raise ImportError("boto3 package is required. Install with: pip install boto3")
        except Exception as e:
            raise ImportError(f"Failed to initialize Bedrock client: {e}")
    
    def generate(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Generate a response using AWS Bedrock."""
        try:
            # Convert messages to Bedrock format
            bedrock_messages = self._convert_messages_to_bedrock(messages)
            
            # Prepare request body based on model
            if "anthropic" in self.model_id.lower():
                request_body = self._prepare_anthropic_request(bedrock_messages, **kwargs)
            elif "amazon" in self.model_id.lower():
                request_body = self._prepare_amazon_request(bedrock_messages, **kwargs)
            elif "meta" in self.model_id.lower():
                request_body = self._prepare_meta_request(bedrock_messages, **kwargs)
            else:
                # Default to Anthropic format
                request_body = self._prepare_anthropic_request(bedrock_messages, **kwargs)
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response.get('body').read())
            
            # Extract content based on model type
            if "anthropic" in self.model_id.lower():
                content = response_body['content'][0]['text']
                usage = response_body.get('usage')
            elif "amazon" in self.model_id.lower():
                content = response_body['completion']
                usage = response_body.get('usage')
            elif "meta" in self.model_id.lower():
                content = response_body['generation']
                usage = response_body.get('usage')
            else:
                content = response_body.get('content', '')
                usage = response_body.get('usage')
            
            return ModelResponse(
                content=content,
                usage=usage,
                finish_reason=response_body.get('stop_reason')
            )
        except Exception as e:
            logger.error(f"AWS Bedrock API error: {e}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response using AWS Bedrock."""
        try:
            # Convert messages to Bedrock format
            bedrock_messages = self._convert_messages_to_bedrock(messages)
            
            # Prepare request body based on model
            if "anthropic" in self.model_id.lower():
                request_body = self._prepare_anthropic_request(bedrock_messages, stream=True, **kwargs)
            elif "amazon" in self.model_id.lower():
                request_body = self._prepare_amazon_request(bedrock_messages, stream=True, **kwargs)
            elif "meta" in self.model_id.lower():
                request_body = self._prepare_meta_request(bedrock_messages, stream=True, **kwargs)
            else:
                request_body = self._prepare_anthropic_request(bedrock_messages, stream=True, **kwargs)
            
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            for event in response.get('body'):
                chunk = json.loads(event['chunk']['bytes'].decode())
                
                if "anthropic" in self.model_id.lower():
                    if chunk['type'] == 'content_block_delta':
                        yield chunk['delta']['text']
                elif "amazon" in self.model_id.lower():
                    if 'completion' in chunk:
                        yield chunk['completion']
                elif "meta" in self.model_id.lower():
                    if 'generation' in chunk:
                        yield chunk['generation']
                else:
                    if 'content' in chunk:
                        yield chunk['content']
        except Exception as e:
            logger.error(f"AWS Bedrock streaming error: {e}")
            raise
    
    def _convert_messages_to_bedrock(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert chat messages to Bedrock format."""
        bedrock_messages = []
        for msg in messages:
            bedrock_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        return bedrock_messages
    
    def _prepare_anthropic_request(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Prepare request body for Anthropic models (Claude)."""
        # Convert to Anthropic format
        system_message = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                user_messages.append({"type": "text", "text": msg["content"]})
            elif msg["role"] == "assistant":
                # Skip assistant messages for now (could be enhanced)
                pass
        
        request_body = {
            "max_completion_tokens": kwargs.get("max_tokens", 4096),
            "messages": [{"role": "user", "content": user_messages}]
        }
        
        if system_message:
            request_body["system"] = system_message
        
        if stream:
            request_body["stream"] = True
        
        return request_body
    
    def _prepare_amazon_request(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Prepare request body for Amazon models (Titan)."""
        # Convert to Amazon format
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"System: {msg['content']}\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n"
        
        request_body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
                "topP": kwargs.get("top_p", 0.9)
            }
        }
        
        return request_body
    
    def _prepare_meta_request(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Prepare request body for Meta models (Llama)."""
        # Convert to Meta format
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"System: {msg['content']}\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n"
        
        request_body = {
            "prompt": prompt,
            "max_gen_len": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9)
        }
        
        return request_body
