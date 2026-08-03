import pytest
from unittest.mock import patch, MagicMock
from app.agent.embedder import SupabaseVectorStore


def test_vector_store_initializes():
    with patch("app.agent.embedder.settings") as mock_settings:
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_key = "test-key"
        store = SupabaseVectorStore()
        assert store is not None


def test_vector_store_requires_config():
    with patch("app.agent.embedder.settings") as mock_settings:
        mock_settings.supabase_url = ""
        mock_settings.supabase_service_key = ""
        with pytest.raises(RuntimeError):
            SupabaseVectorStore()
