"""Models for user authentication tokens."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, SecretStr


class TokenType(str, Enum):
    """Enum for token types."""

    OAUTH = "oauth"
    API = "api"


class TokenProvider(str, Enum):
    """Enum for token providers."""

    DEXCOM = "dexcom"
    INTERNAL = "internal"


class UserToken(BaseModel):
    """Model for storing user authentication tokens."""

    user_id: str = Field(..., description="Unique identifier for the user")
    provider: TokenProvider = Field(..., description="Token provider (e.g., Dexcom)")
    token_type: TokenType = Field(TokenType.OAUTH, description="Type of token")
    access_token: SecretStr = Field(..., description="Access token for API calls")
    refresh_token: Optional[SecretStr] = Field(None, description="Refresh token for obtaining new access tokens")
    expires_at: datetime = Field(..., description="Timestamp when the access token expires")
    scope: str = Field("", description="OAuth scope for the token")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the token was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the token was last updated")
    
    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, value: datetime) -> datetime:
        """Validate that the expiration timestamp is in the future."""
        if value <= datetime.utcnow():
            raise ValueError("Token expiration must be in the future")
        return value
    
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        # Add a 30-second buffer to account for latency and clock differences
        buffer_time = timedelta(seconds=30)
        return datetime.utcnow() >= (self.expires_at - buffer_time)
    
    def expires_soon(self, threshold_minutes: int = 10) -> bool:
        """Check if the token will expire soon."""
        threshold = datetime.utcnow() + timedelta(minutes=threshold_minutes)
        return threshold >= self.expires_at
    
    def to_dynamodb_item(self) -> dict:
        """Convert the model to a DynamoDB item."""
        # Convert to dictionary and handle special types
        item = self.model_dump()
        
        # Handle SecretStr values
        item["access_token"] = self.access_token.get_secret_value()
        if self.refresh_token:
            item["refresh_token"] = self.refresh_token.get_secret_value()
        
        # Convert datetime to ISO format strings
        item["expires_at"] = item["expires_at"].isoformat()
        item["created_at"] = item["created_at"].isoformat()
        item["updated_at"] = item["updated_at"].isoformat()
        
        # Convert enum values to strings
        item["provider"] = item["provider"].value
        item["token_type"] = item["token_type"].value
        
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "UserToken":
        """Create a UserToken instance from a DynamoDB item."""
        # Parse dates from ISO format
        expires_at = datetime.fromisoformat(item["expires_at"])
        created_at = datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.utcnow()
        updated_at = datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else datetime.utcnow()
        
        # Parse enums from strings
        provider = TokenProvider(item["provider"])
        token_type = TokenType(item.get("token_type", TokenType.OAUTH.value))
        
        return cls(
            user_id=item["user_id"],
            provider=provider,
            token_type=token_type,
            access_token=SecretStr(item["access_token"]),
            refresh_token=SecretStr(item["refresh_token"]) if "refresh_token" in item and item["refresh_token"] else None,
            expires_at=expires_at,
            scope=item.get("scope", ""),
            created_at=created_at,
            updated_at=updated_at
        ) 
