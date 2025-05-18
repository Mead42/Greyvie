"""Repository for user authentication tokens."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from pydantic import SecretStr

from src.data.dynamodb import get_dynamodb_client
from src.models.tokens import UserToken, TokenProvider
from src.utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TokenRepository:
    """Repository for user tokens in DynamoDB."""

    def __init__(self):
        """Initialize the repository."""
        self.dynamodb = get_dynamodb_client()
        self.table_name = settings.dynamodb_user_tokens_table
    
    def create(self, token: UserToken) -> UserToken:
        """
        Create a new user token.
        
        Args:
            token: The token to create
            
        Returns:
            UserToken: The created token
        """
        item = token.to_dynamodb_item()
        try:
            self.dynamodb.put_item(self.table_name, item)
            return token
        except ClientError as e:
            logger.error(f"Error creating user token: {e}")
            raise
    
    def get_by_user_and_provider(self, user_id: str, provider: TokenProvider) -> Optional[UserToken]:
        """
        Get a token by user ID and provider.
        
        Args:
            user_id: The user ID
            provider: The token provider
            
        Returns:
            Optional[UserToken]: The token, or None if not found
        """
        key = {
            "user_id": user_id,
            "provider": provider.value
        }
        
        try:
            item = self.dynamodb.get_item(self.table_name, key)
            if item:
                return UserToken.from_dynamodb_item(item)
            return None
        except ClientError as e:
            logger.error(f"Error getting user token: {e}")
            raise
    
    def get_tokens_by_user(self, user_id: str) -> List[UserToken]:
        """
        Get all tokens for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[UserToken]: The list of tokens
        """
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                key_condition_expression=Key("user_id").eq(user_id),
                expression_attribute_values={}
            )
            
            items = result.get("Items", [])
            return [UserToken.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying user tokens: {e}")
            raise
    
    def update(self, token: UserToken) -> UserToken:
        """
        Update an existing token.
        
        Args:
            token: The token to update
            
        Returns:
            UserToken: The updated token
        """
        token.updated_at = datetime.utcnow()
        item = token.to_dynamodb_item()
        
        try:
            self.dynamodb.put_item(self.table_name, item)
            return token
        except ClientError as e:
            logger.error(f"Error updating user token: {e}")
            raise
    
    def update_token_values(
        self, 
        user_id: str, 
        provider: TokenProvider,
        access_token: SecretStr,
        refresh_token: Optional[SecretStr] = None,
        expires_at: Optional[datetime] = None,
        scope: Optional[str] = None
    ) -> Optional[UserToken]:
        """
        Update the values of an existing token.
        
        Args:
            user_id: The user ID
            provider: The token provider
            access_token: The new access token
            refresh_token: The new refresh token (optional)
            expires_at: The new expiration timestamp (optional)
            scope: The new scope (optional)
            
        Returns:
            Optional[UserToken]: The updated token, or None if not found
        """
        # Get the existing token
        token = self.get_by_user_and_provider(user_id, provider)
        if not token:
            return None
        
        # Update the values
        token.access_token = access_token
        if refresh_token:
            token.refresh_token = refresh_token
        if expires_at:
            token.expires_at = expires_at
        if scope:
            token.scope = scope
        
        # Save the updated token
        return self.update(token)
    
    def delete(self, user_id: str, provider: TokenProvider) -> bool:
        """
        Delete a token.
        
        Args:
            user_id: The user ID
            provider: The token provider
            
        Returns:
            bool: True if the deletion was successful
        """
        key = {
            "user_id": user_id,
            "provider": provider.value
        }
        
        try:
            self.dynamodb.delete_item(self.table_name, key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting user token: {e}")
            raise
    
    def delete_tokens_by_user(self, user_id: str) -> int:
        """
        Delete all tokens for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            int: The number of deleted tokens
        """
        try:
            # Get all tokens for the user
            tokens = self.get_tokens_by_user(user_id)
            
            # Delete them one by one
            count = 0
            for token in tokens:
                self.delete(token.user_id, token.provider)
                count += 1
            
            return count
        except ClientError as e:
            logger.error(f"Error deleting user tokens: {e}")
            raise
    
    def get_expired_tokens(self) -> List[UserToken]:
        """
        Get all expired tokens.
        
        Returns:
            List[UserToken]: The list of expired tokens
        """
        try:
            # Unfortunately, DynamoDB doesn't support scanning with conditions on non-key attributes efficiently
            # We'll need to do a full scan and filter in the application
            now = datetime.utcnow()
            
            result = self.dynamodb.scan(
                table_name=self.table_name
            )
            
            items = result.get("Items", [])
            tokens = [UserToken.from_dynamodb_item(item) for item in items]
            
            # Filter expired tokens
            expired_tokens = [token for token in tokens if token.is_expired()]
            
            return expired_tokens
        except ClientError as e:
            logger.error(f"Error scanning for expired tokens: {e}")
            raise


# Singleton instance
_token_repository: Optional[TokenRepository] = None


def get_token_repository() -> TokenRepository:
    """
    Get a singleton instance of the token repository.
    
    Returns:
        TokenRepository: The token repository
    """
    global _token_repository
    if _token_repository is None:
        _token_repository = TokenRepository()
    return _token_repository 