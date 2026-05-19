import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from irpf_processor.infrastructure.persistence import database


@pytest.fixture
def reset_database_state():
    original_client = database._client
    original_db = database._database
    database._client = None
    database._database = None
    yield
    database._client = original_client
    database._database = original_db


class TestInitDatabase:

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.database.get_settings")
    @patch("irpf_processor.infrastructure.persistence.database.AsyncIOMotorClient")
    @patch("irpf_processor.infrastructure.persistence.database._create_indexes")
    async def test_init_database_creates_connection(
        self, mock_create_indexes, mock_client, mock_settings, reset_database_state
    ):
        mock_settings.return_value = MagicMock(
            mongo_uri="mongodb://localhost:27017",
            mongo_db="test_db"
        )

        mock_client_instance = MagicMock()
        mock_client_instance.admin.command = AsyncMock(return_value={"ok": 1})
        mock_client_instance.__getitem__ = MagicMock(return_value=MagicMock())
        mock_client.return_value = mock_client_instance

        mock_create_indexes.return_value = AsyncMock()()

        await database.init_database()

        mock_client.assert_called_once_with("mongodb://localhost:27017")
        mock_client_instance.admin.command.assert_called_once_with("ping")

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.database.get_settings")
    @patch("irpf_processor.infrastructure.persistence.database.AsyncIOMotorClient")
    @patch("irpf_processor.infrastructure.persistence.database._create_indexes")
    async def test_init_database_calls_create_indexes(
        self, mock_create_indexes, mock_client, mock_settings, reset_database_state
    ):
        mock_settings.return_value = MagicMock(
            mongo_uri="mongodb://localhost:27017",
            mongo_db="test_db"
        )

        mock_client_instance = MagicMock()
        mock_client_instance.admin.command = AsyncMock(return_value={"ok": 1})
        mock_client_instance.__getitem__ = MagicMock(return_value=MagicMock())
        mock_client.return_value = mock_client_instance

        mock_create_indexes.return_value = AsyncMock()()

        await database.init_database()

        mock_create_indexes.assert_called_once()


class TestGetDatabase:

    @pytest.mark.asyncio
    async def test_get_database_returns_database_when_initialized(self, reset_database_state):
        mock_db = MagicMock()
        database._database = mock_db

        result = await database.get_database()

        assert result == mock_db

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.database.init_database")
    async def test_get_database_initializes_when_none(self, mock_init, reset_database_state):
        mock_db = MagicMock()
        database._database = None

        async def set_db():
            database._database = mock_db

        mock_init.side_effect = set_db

        result = await database.get_database()

        mock_init.assert_called_once()


class TestCloseDatabase:

    @pytest.mark.asyncio
    async def test_close_database_closes_client(self, reset_database_state):
        mock_client = MagicMock()
        database._client = mock_client
        database._database = MagicMock()

        await database.close_database()

        mock_client.close.assert_called_once()
        assert database._client is None
        assert database._database is None

    @pytest.mark.asyncio
    async def test_close_database_does_nothing_when_not_initialized(self, reset_database_state):
        database._client = None
        database._database = None

        await database.close_database()

        assert database._client is None
        assert database._database is None


class TestCreateIndexes:

    @pytest.mark.asyncio
    async def test_create_indexes_creates_document_indexes(self):
        mock_db = MagicMock()
        mock_documents_collection = MagicMock()
        mock_documents_collection.create_index = AsyncMock()
        mock_extraction_collection = MagicMock()
        mock_extraction_collection.create_index = AsyncMock()

        mock_db.__getitem__.side_effect = lambda name: {
            "documents": mock_documents_collection,
            "extraction_results": mock_extraction_collection,
        }.get(name, MagicMock())

        await database._create_indexes(mock_db)

        assert mock_documents_collection.create_index.call_count >= 3
        assert mock_extraction_collection.create_index.call_count >= 5

    @pytest.mark.asyncio
    async def test_create_indexes_creates_unique_tenant_document_index(self):
        mock_db = MagicMock()
        mock_documents_collection = MagicMock()
        mock_documents_collection.create_index = AsyncMock()
        mock_extraction_collection = MagicMock()
        mock_extraction_collection.create_index = AsyncMock()

        mock_db.__getitem__.side_effect = lambda name: {
            "documents": mock_documents_collection,
            "extraction_results": mock_extraction_collection,
        }.get(name, MagicMock())

        await database._create_indexes(mock_db)

        call_args_list = mock_documents_collection.create_index.call_args_list
        unique_index_call = next(
            (call for call in call_args_list if call[1].get("unique") is True),
            None
        )
        assert unique_index_call is not None


class TestDatabaseModule:

    def test_module_global_variables_exist(self):
        assert hasattr(database, "_client")
        assert hasattr(database, "_database")

    def test_init_database_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(database.init_database)

    def test_get_database_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(database.get_database)

    def test_close_database_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(database.close_database)

    def test_create_indexes_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(database._create_indexes)
