"""
Tests for Notion client functionality.
"""

import pytest
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from notion_client.errors import APIResponseError, RequestTimeoutError

from src.core.notion_client import NotionClient
from src.utils.error_handling import APIError


class TestNotionClient:
    """Tests for NotionClient functionality"""
    
    @pytest.fixture
    def mock_token(self):
        """Mock Notion API token"""
        return "secret_test_token_123"
    
    @pytest.fixture
    def notion_client(self, mock_token):
        """Create NotionClient instance with mocked client"""
        with patch('src.core.notion_client.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            client = NotionClient(mock_token)
            client.client = mock_client
            return client
    
    @pytest.fixture
    def sample_page_data(self):
        """Sample page data for testing"""
        return {
            "object": "page",
            "id": "page_id_123",
            "created_time": "2023-01-01T00:00:00.000Z",
            "last_edited_time": "2023-01-01T00:00:00.000Z",
            "properties": {
                "title": {
                    "id": "title",
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": "Test Page"},
                            "plain_text": "Test Page"
                        }
                    ]
                }
            }
        }
    
    @pytest.fixture
    def sample_database_data(self):
        """Sample database data for testing"""
        return {
            "object": "database",
            "id": "database_id_123",
            "title": [
                {
                    "type": "text",
                    "text": {"content": "Test Database"},
                    "plain_text": "Test Database"
                }
            ],
            "properties": {
                "Name": {
                    "id": "title",
                    "type": "title",
                    "title": {}
                },
                "Date": {
                    "id": "date",
                    "type": "date",
                    "date": {}
                }
            }
        }

    def test_init_success(self, mock_token):
        """Test successful NotionClient initialization"""
        with patch('src.core.notion_client.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            client = NotionClient(mock_token)
            
            assert client.token == mock_token
            assert client.client == mock_client
            assert hasattr(client, 'logger')
            mock_client_class.assert_called_once_with(auth=mock_token)

    def test_init_empty_token(self):
        """Test initialization with empty token"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            NotionClient("")

    def test_init_none_token(self):
        """Test initialization with None token"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            NotionClient(None)

    @patch('src.core.notion_client.Client')
    def test_setup_client_success(self, mock_client_class, mock_token):
        """Test successful client setup"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = NotionClient(mock_token)
        
        assert client.client == mock_client
        mock_client_class.assert_called_once_with(auth=mock_token)

    @patch('src.core.notion_client.Client')
    def test_setup_client_failure(self, mock_client_class, mock_token):
        """Test client setup failure"""
        mock_client_class.side_effect = Exception("Connection failed")
        
        with pytest.raises(APIError):
            NotionClient(mock_token)

    def test_test_connection_success(self, notion_client):
        """Test successful connection test"""
        notion_client.client.users.me.return_value = {
            "object": "user",
            "id": "user_id_123",
            "name": "Test User"
        }
        
        result = notion_client._test_connection()
        
        assert result is True
        notion_client.client.users.me.assert_called_once()

    def test_test_connection_failure(self, notion_client):
        """Test connection test failure"""
        notion_client.client.users.me.side_effect = APIResponseError(
            response=Mock(status_code=401),
            message="Unauthorized"
        )
        
        result = notion_client._test_connection()
        
        assert result is False

    def test_create_page_success(self, notion_client, sample_page_data):
        """Test successful page creation"""
        notion_client.client.pages.create.return_value = sample_page_data
        
        result = notion_client.create_page(
            parent_id="database_id_123",
            title="Test Page",
            content="# Test Content\n\nThis is a test page."
        )
        
        assert result == sample_page_data
        notion_client.client.pages.create.assert_called_once()
        
        # Verify the call arguments
        call_args = notion_client.client.pages.create.call_args[1]
        assert call_args["parent"]["database_id"] == "database_id_123"
        assert "properties" in call_args
        assert "children" in call_args

    def test_create_page_with_properties(self, notion_client, sample_page_data):
        """Test page creation with custom properties"""
        notion_client.client.pages.create.return_value = sample_page_data
        
        properties = {
            "Date": {
                "date": {
                    "start": "2023-01-01"
                }
            },
            "Tags": {
                "multi_select": [
                    {"name": "meeting"},
                    {"name": "important"}
                ]
            }
        }
        
        result = notion_client.create_page(
            parent_id="database_id_123",
            title="Test Page",
            content="Test content",
            properties=properties
        )
        
        assert result == sample_page_data
        call_args = notion_client.client.pages.create.call_args[1]
        assert "Date" in call_args["properties"]
        assert "Tags" in call_args["properties"]

    def test_create_page_api_error(self, notion_client):
        """Test page creation with API error"""
        notion_client.client.pages.create.side_effect = APIResponseError(
            response=Mock(status_code=400),
            message="Bad request"
        )
        
        with pytest.raises(APIError):
            notion_client.create_page(
                parent_id="invalid_id",
                title="Test Page",
                content="Test content"
            )

    def test_update_page_content_only(self, notion_client, sample_page_data):
        """Test page update with content only"""
        notion_client.client.blocks.children.list.return_value = {
            "results": [{"id": "block_1"}, {"id": "block_2"}]
        }
        notion_client.client.blocks.delete.return_value = None
        notion_client.client.blocks.children.append.return_value = None
        notion_client.client.pages.retrieve.return_value = sample_page_data
        
        result = notion_client.update_page(
            page_id="page_id_123",
            content="# Updated Content\n\nThis is updated content."
        )
        
        assert result == sample_page_data
        notion_client.client.blocks.children.append.assert_called_once()

    def test_update_page_properties_only(self, notion_client, sample_page_data):
        """Test page update with properties only"""
        notion_client.client.pages.update.return_value = sample_page_data
        
        properties = {
            "Status": {
                "select": {
                    "name": "Completed"
                }
            }
        }
        
        result = notion_client.update_page(
            page_id="page_id_123",
            properties=properties
        )
        
        assert result == sample_page_data
        notion_client.client.pages.update.assert_called_once_with(
            page_id="page_id_123",
            properties=properties
        )

    def test_update_page_both_content_and_properties(self, notion_client, sample_page_data):
        """Test page update with both content and properties"""
        notion_client.client.blocks.children.list.return_value = {"results": []}
        notion_client.client.blocks.children.append.return_value = None
        notion_client.client.pages.update.return_value = sample_page_data
        notion_client.client.pages.retrieve.return_value = sample_page_data
        
        properties = {"Status": {"select": {"name": "Updated"}}}
        
        result = notion_client.update_page(
            page_id="page_id_123",
            content="Updated content",
            properties=properties
        )
        
        assert result == sample_page_data
        notion_client.client.pages.update.assert_called_once()
        notion_client.client.blocks.children.append.assert_called_once()

    def test_get_database_info_success(self, notion_client, sample_database_data):
        """Test successful database info retrieval"""
        notion_client.client.databases.retrieve.return_value = sample_database_data
        
        result = notion_client.get_database_info("database_id_123")
        
        assert result == sample_database_data
        notion_client.client.databases.retrieve.assert_called_once_with(
            database_id="database_id_123"
        )

    def test_get_database_info_not_found(self, notion_client):
        """Test database info retrieval with not found error"""
        notion_client.client.databases.retrieve.side_effect = APIResponseError(
            response=Mock(status_code=404),
            message="Database not found"
        )
        
        with pytest.raises(APIError):
            notion_client.get_database_info("nonexistent_id")

    def test_query_database_basic(self, notion_client):
        """Test basic database query"""
        query_result = {
            "results": [
                {"id": "page_1", "properties": {}},
                {"id": "page_2", "properties": {}}
            ],
            "has_more": False
        }
        notion_client.client.databases.query.return_value = query_result
        
        result = notion_client.query_database("database_id_123")
        
        assert result == query_result
        notion_client.client.databases.query.assert_called_once_with(
            database_id="database_id_123",
            page_size=100
        )

    def test_query_database_with_filters_and_sorts(self, notion_client):
        """Test database query with filters and sorts"""
        query_result = {"results": [], "has_more": False}
        notion_client.client.databases.query.return_value = query_result
        
        filter_conditions = {
            "property": "Status",
            "select": {
                "equals": "Active"
            }
        }
        
        sorts = [
            {
                "property": "Date",
                "direction": "descending"
            }
        ]
        
        result = notion_client.query_database(
            database_id="database_id_123",
            filter_conditions=filter_conditions,
            sorts=sorts,
            page_size=50
        )
        
        assert result == query_result
        call_args = notion_client.client.databases.query.call_args[1]
        assert call_args["filter"] == filter_conditions
        assert call_args["sorts"] == sorts
        assert call_args["page_size"] == 50

    def test_markdown_to_blocks_simple(self, notion_client):
        """Test markdown to blocks conversion with simple content"""
        markdown = "# Heading 1\n\nThis is a paragraph.\n\n## Heading 2\n\n- List item 1\n- List item 2"
        
        result = notion_client._markdown_to_blocks(markdown)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check for heading block
        heading_blocks = [block for block in result if block.get("type") == "heading_1"]
        assert len(heading_blocks) > 0
        
        # Check for paragraph block
        paragraph_blocks = [block for block in result if block.get("type") == "paragraph"]
        assert len(paragraph_blocks) > 0

    def test_markdown_to_blocks_empty(self, notion_client):
        """Test markdown to blocks conversion with empty content"""
        result = notion_client._markdown_to_blocks("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_markdown_to_blocks_complex(self, notion_client):
        """Test markdown to blocks conversion with complex content"""
        markdown = """# Meeting Minutes

## Attendees
- John Doe
- Jane Smith

## Agenda
1. Project updates
2. Budget review
3. Next steps

## Notes
This is a **bold** text and this is *italic*.

### Action Items
- [ ] Task 1
- [x] Task 2 (completed)

## Code Example
```python
def hello():
    print("Hello, World!")
```

> This is a quote block.
"""
        
        result = notion_client._markdown_to_blocks(markdown)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check for various block types
        block_types = [block.get("type") for block in result]
        assert "heading_1" in block_types
        assert "heading_2" in block_types
        assert "bulleted_list_item" in block_types or "paragraph" in block_types

    def test_clear_page_content_success(self, notion_client):
        """Test successful page content clearing"""
        notion_client.client.blocks.children.list.return_value = {
            "results": [
                {"id": "block_1", "type": "paragraph"},
                {"id": "block_2", "type": "heading_1"}
            ]
        }
        notion_client.client.blocks.delete.return_value = None
        
        notion_client._clear_page_content("page_id_123")
        
        assert notion_client.client.blocks.delete.call_count == 2
        notion_client.client.blocks.delete.assert_any_call(block_id="block_1")
        notion_client.client.blocks.delete.assert_any_call(block_id="block_2")

    def test_clear_page_content_empty_page(self, notion_client):
        """Test clearing content of empty page"""
        notion_client.client.blocks.children.list.return_value = {"results": []}
        
        notion_client._clear_page_content("page_id_123")
        
        notion_client.client.blocks.delete.assert_not_called()

    @pytest.mark.parametrize("id_string,expected", [
        ("12345678-1234-1234-1234-123456789012", True),
        ("123456781234123412341234567890ab", True),
        ("invalid-id", False),
        ("", False),
        ("12345", False),
        ("12345678-1234-1234-1234-12345678901", False),  # Too short
        ("12345678-1234-1234-1234-1234567890123", False),  # Too long
    ])
    def test_is_database_id(self, notion_client, id_string, expected):
        """Test database ID validation"""
        result = notion_client._is_database_id(id_string)
        assert result == expected

    def test_extract_title_success(self, notion_client):
        """Test successful title extraction"""
        title_array = [
            {
                "type": "text",
                "text": {"content": "Meeting Minutes"},
                "plain_text": "Meeting Minutes"
            },
            {
                "type": "text",
                "text": {"content": " - January 2023"},
                "plain_text": " - January 2023"
            }
        ]
        
        result = notion_client._extract_title(title_array)
        
        assert result == "Meeting Minutes - January 2023"

    def test_extract_title_empty_array(self, notion_client):
        """Test title extraction with empty array"""
        result = notion_client._extract_title([])
        
        assert result == ""

    def test_extract_title_none_input(self, notion_client):
        """Test title extraction with None input"""
        result = notion_client._extract_title(None)
        
        assert result == ""

    def test_create_meeting_minutes_page_success(self, notion_client, sample_page_data):
        """Test successful meeting minutes page creation"""
        notion_client.client.pages.create.return_value = sample_page_data
        
        meeting_date = datetime(2023, 1, 15, 14, 30)
        participants = ["John Doe", "Jane Smith", "Bob Johnson"]
        tags = ["meeting", "project-alpha", "quarterly"]
        
        result = notion_client.create_meeting_minutes_page(
            database_id="database_id_123",
            title="Q1 Project Review",
            minutes_content="# Meeting Summary\n\nDiscussed project progress...",
            meeting_date=meeting_date,
            participants=participants,
            tags=tags
        )
        
        assert result == sample_page_data
        notion_client.client.pages.create.assert_called_once()
        
        # Verify the call arguments
        call_args = notion_client.client.pages.create.call_args[1]
        assert call_args["parent"]["database_id"] == "database_id_123"
        
        # Check properties
        properties = call_args["properties"]
        assert "Title" in properties
        assert "Date" in properties
        assert "Participants" in properties
        assert "Tags" in properties

    def test_create_meeting_minutes_page_minimal(self, notion_client, sample_page_data):
        """Test meeting minutes page creation with minimal parameters"""
        notion_client.client.pages.create.return_value = sample_page_data
        
        result = notion_client.create_meeting_minutes_page(
            database_id="database_id_123",
            title="Simple Meeting",
            minutes_content="Basic meeting notes."
        )
        
        assert result == sample_page_data
        call_args = notion_client.client.pages.create.call_args[1]
        
        # Should have default date (today)
        assert "Date" in call_args["properties"]
        # Should have empty participants and tags
        assert "Participants" in call_args["properties"]
        assert "Tags" in call_args["properties"]

    def test_get_client_info_success(self, notion_client):
        """Test successful client info retrieval"""
        user_info = {
            "object": "user",
            "id": "user_id_123",
            "name": "Test User",
            "avatar_url": "https://example.com/avatar.jpg",
            "type": "person",
            "person": {
                "email": "test@example.com"
            }
        }
        notion_client.client.users.me.return_value = user_info
        
        result = notion_client.get_client_info()
        
        assert result == user_info
        notion_client.client.users.me.assert_called_once()

    def test_get_client_info_error(self, notion_client):
        """Test client info retrieval with error"""
        notion_client.client.users.me.side_effect = APIResponseError(
            response=Mock(status_code=401),
            message="Unauthorized"
        )
        
        with pytest.raises(APIError):
            notion_client.get_client_info()

    def test_api_timeout_handling(self, notion_client):
        """Test handling of API timeout errors"""
        notion_client.client.pages.create.side_effect = RequestTimeoutError("Request timeout")
        
        with pytest.raises(APIError, match="Request timeout"):
            notion_client.create_page(
                parent_id="database_id_123",
                title="Test Page",
                content="Test content"
            )

    def test_retry_mechanism(self, notion_client, sample_page_data):
        """Test retry mechanism for transient errors"""
        # First call fails, second succeeds
        notion_client.client.pages.create.side_effect = [
            RequestTimeoutError("Temporary timeout"),
            sample_page_data
        ]
        
        with patch('src.core.notion_client.api_call_with_retry') as mock_retry:
            mock_retry.return_value = sample_page_data
            
            result = notion_client.create_page(
                parent_id="database_id_123",
                title="Test Page",
                content="Test content"
            )
            
            assert result == sample_page_data
            mock_retry.assert_called_once()

    def test_large_content_handling(self, notion_client, sample_page_data):
        """Test handling of large content that might exceed Notion limits"""
        # Create a large markdown content (simulate a very long meeting transcript)
        large_content = "# Large Meeting\n\n" + "This is a very long paragraph. " * 1000
        
        notion_client.client.pages.create.return_value = sample_page_data
        
        result = notion_client.create_page(
            parent_id="database_id_123",
            title="Large Meeting Minutes",
            content=large_content
        )
        
        assert result == sample_page_data
        # Verify that the content was processed (blocks were created)
        call_args = notion_client.client.pages.create.call_args[1]
        assert "children" in call_args
        assert len(call_args["children"]) > 0