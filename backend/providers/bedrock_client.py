"""
AWS Bedrock Provider Client for Claude models.

This module provides a secure, resilient client for interacting with
AWS Bedrock models (Claude, etc.) using boto3.
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from providers.base_provider_client import BaseProviderClient

logger = logging.getLogger(__name__)


class BedrockConfig:
    """Configuration for AWS Bedrock client."""
    
    # Region for Bedrock
    REGION_NAME: str = os.getenv("AWS_REGION", "us-east-1")
    
    # Credentials - prefer explicit env vars
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", 
                                        os.getenv("AWS_Access_key", ""))
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY",
                                            os.getenv("AWS_Secret_access_key", ""))
    
    # Bearer token for Bedrock (alternative auth)
    BEARER_TOKEN: str = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
    
    # Model configurations
    DEFAULT_MODEL: str = "anthropic.claude-3-5-sonnet-20241022"
    CLAUDE_OPUS_MODEL: str = "anthropic.claude-opus-4-20240307"
    CLAUDE_SONNET_MODEL: str = "anthropic.claude-3-5-sonnet-20241022"
    CLAUDE_HAIKU_MODEL: str = "anthropic.claude-haiku-3-20240307"
    
    # Runtime settings
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    TIMEOUT: int = 60  # seconds


class BedrockClient(BaseProviderClient):
    """
    Client for AWS Bedrock Runtime.
    
    Supports both IAM-based authentication and Bearer token authentication.
    Provides methods for invoking Claude models.
    """
    
    def __init__(self, config: Optional[BedrockConfig] = None):
        """Initialize the Bedrock client with configuration."""
        self.config = config or BedrockConfig()
        super().__init__("bedrock", self.config)
        
        # Initialize boto3 client with retry configuration
        self._client = self._create_bedrock_client()
        
        # Validate credentials on init
        self._validate_credentials()
    
    def _create_bedrock_client(self):
        """Create boto3 Bedrock Runtime client with secure configuration."""
        try:
            # Configure client with retry and timeout settings
            client_config = Config(
                region_name=self.config.REGION_NAME,
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                connect_timeout=30,
                read_timeout=self.config.TIMEOUT
            )
            
            # Use IAM credentials if available
            if self.config.AWS_ACCESS_KEY_ID and self.config.AWS_SECRET_ACCESS_KEY:
                logger.info("Using IAM credentials for Bedrock authentication")
                return boto3.client(
                    "bedrock-runtime",
                    config=client_config,
                    aws_access_key_id=self.config.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=self.config.AWS_SECRET_ACCESS_KEY
                )
            
            # Fall back to default credential chain (env vars, config file, etc.)
            logger.info("Using default credential chain for Bedrock")
            return boto3.client("bedrock-runtime", config=client_config)
            
        except Exception as e:
            logger.error(f"Failed to create Bedrock client: {e}")
            raise
    
    def _validate_credentials(self):
        """Validate that credentials are properly configured."""
        has_iam = bool(self.config.AWS_ACCESS_KEY_ID and self.config.AWS_SECRET_ACCESS_KEY)
        has_bearer = bool(self.config.BEARER_TOKEN)
        
        if not has_iam and not has_bearer:
            logger.warning("No AWS credentials found for Bedrock. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_BEARER_TOKEN_BEDROCK")
    
    def _prepare_body(self, messages: List[Dict[str, str]], 
                      max_tokens: Optional[int] = None,
                      temperature: Optional[float] = None,
                      **kwargs) -> str:
        """Prepare the request body for Claude models."""
        body = {
            "messages": messages,
            "max_tokens": max_tokens or self.config.MAX_TOKENS,
            "temperature": temperature or self.config.TEMPERATURE,
            **kwargs
        }
        return json.dumps(body)
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the Bedrock response into a structured format."""
        try:
            body = json.loads(response["body"].read())
            
            return {
                "content": body.get("content", []),
                "stop_reason": body.get("stop_reason"),
                "usage": body.get("usage", {}),
                "model_id": response.get("modelId"),
                "timestamp": datetime.utcnow().isoformat()
            }
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Bedrock response: {e}")
            raise ValueError(f"Invalid response from Bedrock: {e}")
    
    async def invoke_claude(self, 
                           messages: List[Dict[str, str]],
                           model_id: Optional[str] = None,
                           max_tokens: Optional[int] = None,
                           temperature: Optional[float] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        Invoke a Claude model via Bedrock.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: Bedrock model ID (defaults to CLAUDE_SONNET_MODEL)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional model parameters
            
        Returns:
            Dict with 'text', 'usage', and metadata
        """
        try:
            body = self._prepare_body(
                messages, max_tokens, temperature, **kwargs
            )
            
            model = model_id or self.config.DEFAULT_MODEL
            
            logger.info(f"Invoking Bedrock model: {model}")
            
            response = self._client.invoke_model(
                modelId=model,
                body=body
            )
            
            parsed = self._parse_response(response)
            
            # Extract text from content
            text = ""
            if parsed.get("content"):
                for block in parsed["content"]:
                    if block.get("type") == "text":
                        text += block.get("text", "")
            
            return {
                "text": text,
                "stop_reason": parsed.get("stop_reason"),
                "usage": parsed.get("usage", {}),
                "model_id": model,
                "timestamp": parsed.get("timestamp")
            }
            
        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            raise
    
    async def invoke_claude_opus(self, 
                                 messages: List[Dict[str, str]],
                                 **kwargs) -> Dict[str, Any]:
        """Invoke Claude Opus 4 model for complex reasoning tasks."""
        return await self.invoke_claude(
            messages=messages,
            model_id=self.config.CLAUDE_OPUS_MODEL,
            **kwargs
        )
    
    async def invoke_claude_sonnet(self,
                                   messages: List[Dict[str, str]],
                                   **kwargs) -> Dict[str, Any]:
        """Invoke Claude Sonnet 3.5 model for balanced performance."""
        return await self.invoke_claude(
            messages=messages,
            model_id=self.config.CLAUDE_SONNET_MODEL,
            **kwargs
        )
    
    async def invoke_claude_haiku(self,
                                  messages: List[Dict[str, str]],
                                  **kwargs) -> Dict[str, Any]:
        """Invoke Claude Haiku 3 model for fast, lightweight tasks."""
        return await self.invoke_claude(
            messages=messages,
            model_id=self.config.CLAUDE_HAIKU_MODEL,
            **kwargs
        )
    
    # Required abstract methods from BaseProviderClient
    async def get_live_status(self, train_number: str, **kwargs) -> Optional[Dict]:
        """Not applicable for Bedrock provider."""
        return None
    
    async def get_seat_availability(self, train_number: str, travel_date: str,
                                    from_station_code: str, to_station_code: str,
                                    class_code: str, quota: str = "GN", 
                                    **kwargs) -> Optional[List[Dict]]:
        """Not applicable for Bedrock provider."""
        return None
    
    async def get_schedule(self, train_number: str, **kwargs) -> Optional[Dict]:
        """Not applicable for Bedrock provider."""
        return None
    
    async def get_fare(self, train_number: str, travel_date: str,
                       from_station_code: str, to_station_code: str,
                       class_code: str, quota: str = "GN") -> Optional[Dict]:
        """Not applicable for Bedrock provider."""
        return None
    
    async def get_pnr_status(self, pnr_number: str) -> Optional[Dict]:
        """Not applicable for Bedrock provider."""
        return None


# Convenience function for quick initialization
def get_bedrock_client() -> BedrockClient:
    """Get a configured Bedrock client instance."""
    return BedrockClient()


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_claude():
        """Test Bedrock client with a simple prompt."""
        client = BedrockClient()
        
        messages = [
            {
                "role": "user",
                "content": "Explain what AWS Bedrock is in 2-3 sentences."
            }
        ]
        
        try:
            response = await client.invoke_claude_sonnet(messages)
            print(f"Response: {response['text']}")
            print(f"Model: {response['model_id']}")
            print(f"Tokens used: {response['usage']}")
        except Exception as e:
            print(f"Error: {e}")
    
    # Run test
    asyncio.run(test_claude())
