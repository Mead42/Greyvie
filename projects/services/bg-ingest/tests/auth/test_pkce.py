"""Tests for the OAuth2 PKCE module."""
import re
import pytest
from src.auth.pkce import (
    generate_code_verifier,
    generate_code_challenge,
    generate_pkce_pair,
)


class TestPkce:
    """Tests for the PKCE implementation."""

    def test_code_verifier_length(self):
        """Test the code verifier has the correct length."""
        # Default length (128)
        verifier = generate_code_verifier()
        assert len(verifier) == 128

        # Custom length
        custom_length = 96
        verifier = generate_code_verifier(custom_length)
        assert len(verifier) == custom_length

    def test_code_verifier_format(self):
        """Test the code verifier has the correct format."""
        verifier = generate_code_verifier()
        # Only allowed characters are used
        assert re.match(r'^[A-Za-z0-9\-._~]+$', verifier) is not None

    def test_code_verifier_randomness(self):
        """Test the code verifier is different each time."""
        verifier1 = generate_code_verifier()
        verifier2 = generate_code_verifier()
        assert verifier1 != verifier2

    def test_code_verifier_length_validation(self):
        """Test that the code verifier length is validated."""
        # Too short
        with pytest.raises(ValueError):
            generate_code_verifier(42)

        # Too long
        with pytest.raises(ValueError):
            generate_code_verifier(129)

    def test_code_challenge_format(self):
        """Test the code challenge has the correct format."""
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        # Challenge should be a base64url string without padding
        assert re.match(r'^[A-Za-z0-9\-_]+$', challenge) is not None
        assert '=' not in challenge

    def test_code_challenge_deterministic(self):
        """Test the code challenge is deterministic for a given verifier."""
        verifier = generate_code_verifier()
        challenge1 = generate_code_challenge(verifier)
        challenge2 = generate_code_challenge(verifier)
        assert challenge1 == challenge2

    def test_code_challenge_different_for_different_verifiers(self):
        """Test the code challenge is different for different verifiers."""
        verifier1 = generate_code_verifier()
        verifier2 = generate_code_verifier()
        challenge1 = generate_code_challenge(verifier1)
        challenge2 = generate_code_challenge(verifier2)
        assert challenge1 != challenge2

    def test_generate_pkce_pair(self):
        """Test the generation of a PKCE verifier and challenge pair."""
        verifier, challenge = generate_pkce_pair()

        # Verify format
        assert re.match(r'^[A-Za-z0-9\-._~]+$', verifier) is not None
        assert re.match(r'^[A-Za-z0-9\-_]+$', challenge) is not None

        # Verify verifier length
        assert len(verifier) == 128

        # Verify challenge matches the verifier
        assert challenge == generate_code_challenge(verifier) 