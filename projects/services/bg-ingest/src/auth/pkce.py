"""
OAuth2 PKCE (Proof Key for Code Exchange) implementation.

This module provides functions for generating cryptographically secure
code verifiers and code challenges for OAuth2 PKCE flow, enhancing
security for the authorization code flow.
"""
import base64
import hashlib
import os
import re


def generate_code_verifier(length: int = 128) -> str:
    """
    Generate a cryptographically secure code verifier for PKCE.
    
    The code verifier is a high-entropy random string using only
    characters [A-Z], [a-z], [0-9], "-", ".", "_", "~".
    
    Args:
        length: Length of the code verifier (43-128 chars). Default is 128.
        
    Returns:
        A random code verifier string.
        
    Raises:
        ValueError: If length is not between 43 and 128.
    """
    if not 43 <= length <= 128:
        raise ValueError("Code verifier length must be between 43 and 128 characters")
    
    # Generate random bytes and encode as URL-safe base64
    random_bytes = os.urandom(length)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
    
    # Remove padding characters and limit to specified length
    code_verifier = re.sub(r'[^a-zA-Z0-9-._~]', '', code_verifier)[:length]
    
    return code_verifier


def generate_code_challenge(code_verifier: str) -> str:
    """
    Generate a code challenge from the code verifier using the S256 method.
    
    The code challenge is derived by taking the SHA-256 hash of the code
    verifier and then encoding it as base64url without padding.
    
    Args:
        code_verifier: The code verifier string to hash.
        
    Returns:
        The code challenge string.
    """
    # Generate SHA-256 hash of the verifier
    code_challenge_digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    
    # Base64url encode the hash
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode('utf-8')
    
    # Remove padding characters
    code_challenge = code_challenge.replace('=', '')
    
    return code_challenge


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate a code verifier and code challenge pair for PKCE.
    
    Returns:
        A tuple of (code_verifier, code_challenge).
    """
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    return code_verifier, code_challenge 