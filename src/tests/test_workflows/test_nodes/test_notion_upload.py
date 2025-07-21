"""
Tests for notion upload workflow node.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

from src.workflows.nodes.notion_upload import (
    upload_notion_node,
    _initialize_notion_client,
    _build_page_data,
    _generate_page_title,
    _build_page_content,
    _create_summary_blocks,
    _create_minutes_blocks,
    _create_quality_blocks,
    _create_metadata_blocks,
    _convert_markdown_to_notion_blocks,
    _parse_rich_text,
    _create_notion_page,
    test_notion_connection,
    get_database_info
)
from src.workflows.state import STTState
from src.utils.error_handling import NotionUploadError


class TestUploadNotionNode:
    """Tests for upload_notion_node functionality"""
    
    @pytest.fixture
    def base_state(self):
        """Create base STT state for testing"""
        return {
            "minutes": "# Meeting Minutes\n\n## Summary\nThis was a productive meeting.",
            "settings": {
                "notion_token": "secret_test_token",
                "notion_database_id": "database_123",
                "upload_to_notion": True
            },
            "class_info": {
                "subject": "Project Meeting",
                "date": "2023-01-15",
                "period": "1限"
            },
            "quality_check_result": {
                "overall_score": 85,
                "confidence": 0.9,
                "issues": []
            },
            "processing_log": [],
            "errors": [],
            "processing_stage": "minutes_complete"
        }
    
    @pytest.fixture
    def mock_notion_client(self):
        """Mock Notion client"""
        client = Mock()
        client.pages.create.return_value = {
            "id": "page_123",
            "url": "https://notion.so/page_123",
            "created_time": "2023-01-15T10:00:00.000Z"
        }
        return client

    @patch('src.workflows.nodes.notion_upload._initialize_notion_client')
    @patch('src.workflows.nodes.notion_upload._create_notion_page')
    def test_upload_notion_node_success(self, mock_create_page, mock_init_client, base_state, mock_notion_client):
        """Test successful Notion upload"""
        mock_init_client.return_value = mock_notion_client
        mock_create_page.return_value = {
            "id": "page_123",
            "url": "https://notion.so/page_123"
        }
        
        result = upload_notion_node(base_state)
        
        assert result["processing_stage"] == "notion_upload"
        assert "notion_page_id" in result
        assert result["notion_page_id"] == "page_123"
        assert "notion_page_url" in result
        assert result["notion_page_url"] == "https://notion.so/page_123"
        assert len(result["processing_log"]) > 0
        assert any("Notion" in log for log in result["processing_log"])
        assert len(result["errors"]) == 0
        
        mock_init_client.assert_called_once_with(base_state["settings"])
        mock_create_page.assert_called_once()

    def test_upload_notion_node_disabled(self, base_state):
        """Test Notion upload when disabled"""
        base_state["settings"]["upload_to_notion"] = False
        
        result = upload_notion_node(base_state)
        
        assert result["processing_stage"] == "notion_upload"
        assert "notion_page_id" not in result
        assert len(result["processing_log"]) > 0
        assert any("スキップ" in log for log in result["processing_log"])
        assert len(result["errors"]) == 0

    def test_upload_notion_node_missing_settings(self, base_state):
        """Test Notion upload with missing settings"""
        del base_state["settings"]["notion_token"]
        
        result = upload_notion_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "Notion設定が不完全です" in result["errors"][0]

    def test_upload_notion_node_missing_minutes(self, base_state):
        """Test Notion upload with missing minutes"""
        del base_state["minutes"]
        
        result = upload_notion_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "議事録が生成されていません" in result["errors"][0]

    @patch('src.workflows.nodes.notion_upload._initialize_notion_client')
    def test_upload_notion_node_client_error(self, mock_init_client, base_state):
        """Test Notion upload with client initialization error"""
        mock_init_client.side_effect = NotionUploadError("Failed to initialize client")
        
        result = upload_notion_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "Notionアップロードエラー" in result["errors"][0]
        assert "Failed to initialize client" in result["errors"][0]

    @patch('src.workflows.nodes.notion_upload._initialize_notion_client')
    @patch('src.workflows.nodes.notion_upload._create_notion_page')
    def test_upload_notion_node_page_creation_error(self, mock_create_page, mock_init_client, base_state, mock_notion_client):
        """Test Notion upload with page creation error"""
        mock_init_client.return_value = mock_notion_client
        mock_create_page.side_effect = NotionUploadError("Failed to create page")
        
        result = upload_notion_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "Notionアップロードエラー" in result["errors"][0]
        assert "Failed to create page" in result["errors"][0]


class TestInitializeNotionClient:
    """Tests for _initialize_notion_client function"""
    
    @pytest.fixture
    def valid_settings(self):
        """Valid Notion settings"""
        return {
            "notion_token": "secret_test_token",
            "notion_database_id": "database_123"
        }

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_initialize_notion_client_success(self, mock_client_class, valid_settings):
        """Test successful Notion client initialization"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        result = _initialize_notion_client(valid_settings)
        
        assert result == mock_client
        mock_client_class.assert_called_once_with(auth="secret_test_token")

    def test_initialize_notion_client_missing_token(self):
        """Test client initialization with missing token"""
        settings = {"notion_database_id": "database_123"}
        
        with pytest.raises(NotionUploadError, match="Notion token is required"):
            _initialize_notion_client(settings)

    def test_initialize_notion_client_empty_token(self):
        """Test client initialization with empty token"""
        settings = {
            "notion_token": "",
            "notion_database_id": "database_123"
        }
        
        with pytest.raises(NotionUploadError, match="Notion token is required"):
            _initialize_notion_client(settings)

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_initialize_notion_client_api_error(self, mock_client_class, valid_settings):
        """Test client initialization with API error"""
        mock_client_class.side_effect = Exception("API connection failed")
        
        with pytest.raises(NotionUploadError, match="Failed to initialize Notion client"):
            _initialize_notion_client(valid_settings)


class TestBuildPageData:
    """Tests for page data building functions"""
    
    @pytest.fixture
    def sample_state(self):
        """Sample state for page data building"""
        return {
            "minutes": "# Meeting Minutes\n\n## Summary\nTest content",
            "class_info": {
                "subject": "Test Meeting",
                "date": "2023-01-15",
                "period": "1限"
            },
            "quality_check_result": {
                "overall_score": 85,
                "confidence": 0.9
            },
            "settings": {
                "notion_database_id": "database_123"
            }
        }

    @patch('src.workflows.nodes.notion_upload._generate_page_title')
    @patch('src.workflows.nodes.notion_upload._build_page_content')
    def test_build_page_data_success(self, mock_build_content, mock_generate_title, sample_state):
        """Test successful page data building"""
        mock_generate_title.return_value = "Test Meeting - 2023-01-15"
        mock_build_content.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        
        result = _build_page_data(sample_state)
        
        assert isinstance(result, dict)
        assert "parent" in result
        assert result["parent"]["database_id"] == "database_123"
        assert "properties" in result
        assert "children" in result
        
        # Check properties
        properties = result["properties"]
        assert "Title" in properties
        assert properties["Title"]["title"][0]["text"]["content"] == "Test Meeting - 2023-01-15"
        assert "Date" in properties
        assert "Subject" in properties
        assert "Period" in properties

    def test_generate_page_title_with_class_info(self):
        """Test page title generation with class info"""
        class_info = {
            "subject": "Project Meeting",
            "date": "2023-01-15",
            "period": "1限"
        }
        state = {"class_info": class_info}
        
        result = _generate_page_title(class_info, state)
        
        assert isinstance(result, str)
        assert "Project Meeting" in result
        assert "2023-01-15" in result

    def test_generate_page_title_missing_info(self):
        """Test page title generation with missing info"""
        class_info = {}
        state = {}
        
        result = _generate_page_title(class_info, state)
        
        assert isinstance(result, str)
        assert len(result) > 0  # Should return default title

    @patch('src.workflows.nodes.notion_upload._create_summary_blocks')
    @patch('src.workflows.nodes.notion_upload._create_minutes_blocks')
    @patch('src.workflows.nodes.notion_upload._create_quality_blocks')
    @patch('src.workflows.nodes.notion_upload._create_metadata_blocks')
    def test_build_page_content_success(self, mock_metadata, mock_quality, mock_minutes, mock_summary, sample_state):
        """Test successful page content building"""
        mock_summary.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        mock_minutes.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        mock_quality.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        mock_metadata.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        
        result = _build_page_content(sample_state)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        mock_summary.assert_called_once()
        mock_minutes.assert_called_once_with(sample_state["minutes"])
        mock_quality.assert_called_once_with(sample_state["quality_check_result"])
        mock_metadata.assert_called_once_with(sample_state)


class TestContentBlocks:
    """Tests for content block creation functions"""

    def test_create_summary_blocks_basic(self):
        """Test basic summary blocks creation"""
        summary = "This is a test summary with key points."
        
        result = _create_summary_blocks(summary)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert any(block.get("type") == "heading_2" for block in result)

    def test_create_summary_blocks_empty(self):
        """Test summary blocks creation with empty summary"""
        result = _create_summary_blocks("")
        
        assert isinstance(result, list)
        assert len(result) > 0  # Should still create header

    def test_create_minutes_blocks_markdown(self):
        """Test minutes blocks creation with markdown"""
        minutes = "# Meeting Minutes\n\n## Agenda\n- Item 1\n- Item 2"
        
        with patch('src.workflows.nodes.notion_upload._convert_markdown_to_notion_blocks') as mock_convert:
            mock_convert.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
            
            result = _create_minutes_blocks(minutes)
            
            assert isinstance(result, list)
            mock_convert.assert_called_once_with(minutes)

    def test_create_quality_blocks_with_results(self):
        """Test quality blocks creation with results"""
        quality_result = {
            "overall_score": 85,
            "confidence": 0.9,
            "issues": ["Minor audio quality issue"],
            "recommendations": ["Use better microphone"]
        }
        
        result = _create_quality_blocks(quality_result)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert any(block.get("type") == "heading_2" for block in result)

    def test_create_quality_blocks_empty(self):
        """Test quality blocks creation with empty results"""
        result = _create_quality_blocks({})
        
        assert isinstance(result, list)
        assert len(result) > 0  # Should still create header

    def test_create_metadata_blocks_complete(self):
        """Test metadata blocks creation with complete state"""
        state = {
            "file_path": "/test/audio.wav",
            "audio_duration": 1800,  # 30 minutes
            "processing_time": 120,  # 2 minutes
            "transcription_method": "AI",
            "class_info": {
                "subject": "Test Meeting",
                "date": "2023-01-15"
            }
        }
        
        result = _create_metadata_blocks(state)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert any(block.get("type") == "heading_2" for block in result)

    def test_create_metadata_blocks_minimal(self):
        """Test metadata blocks creation with minimal state"""
        state = {}
        
        result = _create_metadata_blocks(state)
        
        assert isinstance(result, list)
        assert len(result) > 0  # Should still create header


class TestMarkdownConversion:
    """Tests for markdown to Notion blocks conversion"""

    def test_convert_markdown_to_notion_blocks_headings(self):
        """Test markdown conversion with headings"""
        markdown = "# Heading 1\n\n## Heading 2\n\n### Heading 3"
        
        result = _convert_markdown_to_notion_blocks(markdown)
        
        assert isinstance(result, list)
        assert len(result) >= 3
        
        # Check for heading blocks
        heading_types = [block.get("type") for block in result]
        assert "heading_1" in heading_types
        assert "heading_2" in heading_types
        assert "heading_3" in heading_types

    def test_convert_markdown_to_notion_blocks_lists(self):
        """Test markdown conversion with lists"""
        markdown = "- Item 1\n- Item 2\n\n1. Numbered 1\n2. Numbered 2"
        
        result = _convert_markdown_to_notion_blocks(markdown)
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check for list blocks
        block_types = [block.get("type") for block in result]
        assert "bulleted_list_item" in block_types or "numbered_list_item" in block_types

    def test_convert_markdown_to_notion_blocks_paragraphs(self):
        """Test markdown conversion with paragraphs"""
        markdown = "This is a paragraph.\n\nThis is another paragraph with **bold** and *italic* text."
        
        result = _convert_markdown_to_notion_blocks(markdown)
        
        assert isinstance(result, list)
        assert len(result) >= 2
        
        # Check for paragraph blocks
        paragraph_blocks = [block for block in result if block.get("type") == "paragraph"]
        assert len(paragraph_blocks) >= 2

    def test_convert_markdown_to_notion_blocks_empty(self):
        """Test markdown conversion with empty content"""
        result = _convert_markdown_to_notion_blocks("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_rich_text_basic(self):
        """Test basic rich text parsing"""
        text = "This is plain text."
        
        result = _parse_rich_text(text)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["text"]["content"] == text
        assert result[0]["annotations"]["bold"] is False

    def test_parse_rich_text_formatting(self):
        """Test rich text parsing with formatting"""
        text = "This is **bold** and *italic* text."
        
        result = _parse_rich_text(text)
        
        assert isinstance(result, list)
        assert len(result) > 1  # Should be split into multiple parts

    def test_parse_rich_text_empty(self):
        """Test rich text parsing with empty text"""
        result = _parse_rich_text("")
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["text"]["content"] == ""


class TestNotionPageCreation:
    """Tests for Notion page creation"""
    
    @pytest.fixture
    def mock_client(self):
        """Mock Notion client"""
        client = Mock()
        client.pages.create.return_value = {
            "id": "page_123",
            "url": "https://notion.so/page_123",
            "created_time": "2023-01-15T10:00:00.000Z"
        }
        return client
    
    @pytest.fixture
    def sample_page_data(self):
        """Sample page data"""
        return {
            "parent": {"database_id": "database_123"},
            "properties": {
                "Title": {
                    "title": [{"text": {"content": "Test Page"}}]
                }
            },
            "children": [
                {"type": "paragraph", "paragraph": {"rich_text": []}}
            ]
        }

    def test_create_notion_page_success(self, mock_client, sample_page_data):
        """Test successful Notion page creation"""
        result = _create_notion_page(mock_client, "database_123", sample_page_data)
        
        assert result["id"] == "page_123"
        assert result["url"] == "https://notion.so/page_123"
        mock_client.pages.create.assert_called_once_with(**sample_page_data)

    def test_create_notion_page_api_error(self, mock_client, sample_page_data):
        """Test Notion page creation with API error"""
        mock_client.pages.create.side_effect = Exception("API Error")
        
        with pytest.raises(NotionUploadError, match="Failed to create Notion page"):
            _create_notion_page(mock_client, "database_123", sample_page_data)

    def test_create_notion_page_invalid_response(self, mock_client, sample_page_data):
        """Test Notion page creation with invalid response"""
        mock_client.pages.create.return_value = {}  # Missing required fields
        
        with pytest.raises(NotionUploadError, match="Invalid response from Notion API"):
            _create_notion_page(mock_client, "database_123", sample_page_data)


class TestUtilityFunctions:
    """Tests for utility functions"""
    
    @pytest.fixture
    def valid_settings(self):
        """Valid Notion settings"""
        return {
            "notion_token": "secret_test_token",
            "notion_database_id": "database_123"
        }

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_test_notion_connection_success(self, mock_client_class, valid_settings):
        """Test successful Notion connection test"""
        mock_client = Mock()
        mock_client.users.me.return_value = {
            "id": "user_123",
            "name": "Test User"
        }
        mock_client_class.return_value = mock_client
        
        result = test_notion_connection(valid_settings)
        
        assert result is True
        mock_client.users.me.assert_called_once()

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_test_notion_connection_failure(self, mock_client_class, valid_settings):
        """Test Notion connection test failure"""
        mock_client = Mock()
        mock_client.users.me.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client
        
        result = test_notion_connection(valid_settings)
        
        assert result is False

    def test_test_notion_connection_missing_token(self):
        """Test connection test with missing token"""
        settings = {"notion_database_id": "database_123"}
        
        result = test_notion_connection(settings)
        
        assert result is False

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_get_database_info_success(self, mock_client_class, valid_settings):
        """Test successful database info retrieval"""
        mock_client = Mock()
        mock_client.databases.retrieve.return_value = {
            "id": "database_123",
            "title": [{"text": {"content": "Test Database"}}],
            "properties": {}
        }
        mock_client_class.return_value = mock_client
        
        result = get_database_info(valid_settings, "database_123")
        
        assert result is not None
        assert result["id"] == "database_123"
        mock_client.databases.retrieve.assert_called_once_with(database_id="database_123")

    @patch('src.workflows.nodes.notion_upload.NotionClient')
    def test_get_database_info_not_found(self, mock_client_class, valid_settings):
        """Test database info retrieval with not found error"""
        mock_client = Mock()
        mock_client.databases.retrieve.side_effect = Exception("Database not found")
        mock_client_class.return_value = mock_client
        
        result = get_database_info(valid_settings, "nonexistent_db")
        
        assert result is None

    def test_get_database_info_missing_token(self):
        """Test database info retrieval with missing token"""
        settings = {"notion_database_id": "database_123"}
        
        result = get_database_info(settings, "database_123")
        
        assert result is None


class TestEdgeCases:
    """Tests for edge cases and error scenarios"""

    def test_upload_notion_node_large_content(self):
        """Test Notion upload with very large content"""
        large_minutes = "# Large Meeting\n\n" + "This is a very long paragraph. " * 1000
        
        state = {
            "minutes": large_minutes,
            "settings": {
                "notion_token": "test_token",
                "notion_database_id": "database_123",
                "upload_to_notion": True
            },
            "class_info": {"subject": "Large Meeting"},
            "processing_log": [],
            "errors": []
        }
        
        with patch('src.workflows.nodes.notion_upload._initialize_notion_client') as mock_init:
            with patch('src.workflows.nodes.notion_upload._create_notion_page') as mock_create:
                mock_init.return_value = Mock()
                mock_create.return_value = {"id": "page_123", "url": "https://notion.so/page_123"}
                
                result = upload_notion_node(state)
                
                assert "notion_page_id" in result
                assert len(result["errors"]) == 0

    def test_markdown_conversion_complex(self):
        """Test markdown conversion with complex formatting"""
        complex_markdown = """
        # Main Title
        
        ## Section 1
        This is a paragraph with **bold**, *italic*, and `code` formatting.
        
        ### Subsection
        - Bullet point 1
        - Bullet point 2 with **bold text**
        
        1. Numbered item 1
        2. Numbered item 2
        
        > This is a blockquote
        
        ```python
        def hello():
            print("Hello, World!")
        ```
        
        [Link text](https://example.com)
        """
        
        result = _convert_markdown_to_notion_blocks(complex_markdown)
        
        assert isinstance(result, list)
        assert len(result) > 5  # Should create multiple blocks
        
        # Check for various block types
        block_types = [block.get("type") for block in result]
        assert "heading_1" in block_types
        assert "heading_2" in block_types
        assert "paragraph" in block_types

    def test_rich_text_parsing_edge_cases(self):
        """Test rich text parsing with edge cases"""
        edge_cases = [
            "**Bold at start** and normal text",
            "Normal text and **bold at end**",
            "**Multiple** **bold** **sections**",
            "*Italic* and **bold** mixed",
            "Text with `inline code` formatting",
            "",  # Empty string
            "   ",  # Whitespace only
            "**",  # Incomplete formatting
            "**bold without closing",
            "Text with\nnewlines\nincluded"
        ]
        
        for text in edge_cases:
            result = _parse_rich_text(text)
            assert isinstance(result, list)
            assert len(result) >= 1