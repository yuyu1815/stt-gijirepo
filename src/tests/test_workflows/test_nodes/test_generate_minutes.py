"""
Tests for generate minutes workflow node.
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime
from typing import Dict, Any

from src.workflows.nodes.minutes_generation import (
    generate_minutes_node,
    _generate_ai_minutes,
    _generate_ai_summary,
    _generate_basic_minutes,
    _generate_basic_summary,
    _build_minutes_prompt,
    _build_summary_prompt,
    _load_minutes_prompt,
    _load_summary_prompt,
    _format_transcription_content,
    _post_process_minutes,
    _convert_format,
    extract_key_points,
    generate_title_from_content
)
from src.workflows.state import STTState
from src.utils.error_handling import APIError


class TestGenerateMinutesNode:
    """Tests for generate_minutes_node functionality"""
    
    @pytest.fixture
    def base_state(self):
        """Create base STT state for testing"""
        return {
            "transcription": "This is a test meeting transcription. We discussed project updates and next steps.",
            "settings": {
                "output_format": "markdown",
                "minutes_type": "detailed",
                "use_ai": True
            },
            "class_info": {
                "period": "1限",
                "subject": "プロジェクト会議",
                "date": "2023-01-15"
            },
            "processing_log": [],
            "errors": [],
            "processing_stage": "transcription_complete"
        }
    
    @pytest.fixture
    def sample_transcription(self):
        """Sample transcription text"""
        return """
        Speaker 1: Good morning everyone. Let's start today's meeting.
        Speaker 2: Thank you. First item on the agenda is project updates.
        Speaker 1: The development team has completed phase 1.
        Speaker 2: Great! What about the testing phase?
        Speaker 1: Testing will begin next week.
        Speaker 2: Any questions or concerns?
        Speaker 1: No major issues. We're on track.
        Speaker 2: Perfect. Let's move to the next item.
        """

    @patch('src.workflows.nodes.minutes_generation._generate_ai_minutes')
    def test_generate_minutes_node_ai_detailed(self, mock_ai_minutes, base_state):
        """Test minutes generation with AI detailed mode"""
        mock_ai_minutes.return_value = "# Meeting Minutes\n\n## Summary\nDetailed AI-generated minutes..."
        
        result = generate_minutes_node(base_state)
        
        assert result["processing_stage"] == "minutes_generation"
        assert "minutes" in result
        assert result["minutes"] == "# Meeting Minutes\n\n## Summary\nDetailed AI-generated minutes..."
        assert len(result["processing_log"]) > 0
        assert any("議事録生成完了" in log for log in result["processing_log"])
        assert len(result["errors"]) == 0
        
        mock_ai_minutes.assert_called_once_with(base_state["transcription"], base_state)

    @patch('src.workflows.nodes.minutes_generation._generate_ai_summary')
    def test_generate_minutes_node_ai_summary(self, mock_ai_summary, base_state):
        """Test minutes generation with AI summary mode"""
        base_state["settings"]["minutes_type"] = "summary"
        mock_ai_summary.return_value = "## Meeting Summary\nBrief AI-generated summary..."
        
        result = generate_minutes_node(base_state)
        
        assert result["processing_stage"] == "minutes_generation"
        assert "minutes" in result
        assert result["minutes"] == "## Meeting Summary\nBrief AI-generated summary..."
        assert len(result["errors"]) == 0
        
        mock_ai_summary.assert_called_once_with(base_state["transcription"], base_state)

    @patch('src.workflows.nodes.minutes_generation._generate_basic_minutes')
    def test_generate_minutes_node_basic_detailed(self, mock_basic_minutes, base_state):
        """Test minutes generation with basic detailed mode"""
        base_state["settings"]["use_ai"] = False
        mock_basic_minutes.return_value = "# Basic Meeting Minutes\n\nBasic formatted minutes..."
        
        result = generate_minutes_node(base_state)
        
        assert result["processing_stage"] == "minutes_generation"
        assert "minutes" in result
        assert result["minutes"] == "# Basic Meeting Minutes\n\nBasic formatted minutes..."
        assert len(result["errors"]) == 0
        
        mock_basic_minutes.assert_called_once_with(base_state["transcription"], base_state)

    @patch('src.workflows.nodes.minutes_generation._generate_basic_summary')
    def test_generate_minutes_node_basic_summary(self, mock_basic_summary, base_state):
        """Test minutes generation with basic summary mode"""
        base_state["settings"]["use_ai"] = False
        base_state["settings"]["minutes_type"] = "summary"
        mock_basic_summary.return_value = "## Basic Summary\nBasic summary text..."
        
        result = generate_minutes_node(base_state)
        
        assert result["processing_stage"] == "minutes_generation"
        assert "minutes" in result
        assert result["minutes"] == "## Basic Summary\nBasic summary text..."
        assert len(result["errors"]) == 0
        
        mock_basic_summary.assert_called_once_with(base_state["transcription"])

    def test_generate_minutes_node_missing_transcription(self, base_state):
        """Test minutes generation with missing transcription"""
        del base_state["transcription"]
        
        result = generate_minutes_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "議事録生成エラー" in result["errors"][0]

    def test_generate_minutes_node_empty_transcription(self, base_state):
        """Test minutes generation with empty transcription"""
        base_state["transcription"] = ""
        
        result = generate_minutes_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "文字起こし結果が空です" in result["errors"][0]

    @patch('src.workflows.nodes.minutes_generation._generate_ai_minutes')
    def test_generate_minutes_node_ai_error(self, mock_ai_minutes, base_state):
        """Test handling of AI generation errors"""
        mock_ai_minutes.side_effect = APIError("AI service unavailable")
        
        result = generate_minutes_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "議事録生成エラー" in result["errors"][0]
        assert "AI service unavailable" in result["errors"][0]

    def test_generate_minutes_node_default_settings(self, base_state):
        """Test minutes generation with default settings"""
        del base_state["settings"]
        
        with patch('src.workflows.nodes.minutes_generation._generate_basic_minutes') as mock_basic:
            mock_basic.return_value = "Default minutes"
            
            result = generate_minutes_node(base_state)
            
            assert "minutes" in result
            mock_basic.assert_called_once()


class TestGenerateAIMinutes:
    """Tests for AI-based minutes generation functions"""
    
    @pytest.fixture
    def sample_state(self):
        """Sample state for AI generation"""
        return {
            "settings": {"output_format": "markdown"},
            "class_info": {"subject": "Test Meeting"},
            "processing_log": []
        }

    @patch('src.workflows.nodes.minutes_generation.genai')
    @patch('src.workflows.nodes.minutes_generation._build_minutes_prompt')
    def test_generate_ai_minutes_success(self, mock_build_prompt, mock_genai, sample_state):
        """Test successful AI minutes generation"""
        mock_build_prompt.return_value = "Generate detailed minutes for: test transcription"
        
        # Mock Gemini API
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "# AI Generated Minutes\n\n## Summary\nDetailed minutes content..."
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        result = _generate_ai_minutes("test transcription", sample_state)
        
        assert result == "# AI Generated Minutes\n\n## Summary\nDetailed minutes content..."
        mock_build_prompt.assert_called_once_with("test transcription", sample_state)
        mock_model.generate_content.assert_called_once()

    @patch('src.workflows.nodes.minutes_generation.genai')
    @patch('src.workflows.nodes.minutes_generation._build_summary_prompt')
    def test_generate_ai_summary_success(self, mock_build_prompt, mock_genai, sample_state):
        """Test successful AI summary generation"""
        mock_build_prompt.return_value = "Generate summary for: test transcription"
        
        # Mock Gemini API
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "## Meeting Summary\nBrief summary content..."
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        result = _generate_ai_summary("test transcription", sample_state)
        
        assert result == "## Meeting Summary\nBrief summary content..."
        mock_build_prompt.assert_called_once_with("test transcription", sample_state)

    @patch('src.workflows.nodes.minutes_generation.genai')
    def test_generate_ai_minutes_api_error(self, mock_genai, sample_state):
        """Test AI minutes generation with API error"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_genai.GenerativeModel.return_value = mock_model
        
        with pytest.raises(APIError):
            _generate_ai_minutes("test transcription", sample_state)

    @patch('src.workflows.nodes.minutes_generation.genai')
    def test_generate_ai_minutes_empty_response(self, mock_genai, sample_state):
        """Test AI minutes generation with empty response"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = ""
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        with pytest.raises(APIError, match="AI応答が空です"):
            _generate_ai_minutes("test transcription", sample_state)


class TestGenerateBasicMinutes:
    """Tests for basic minutes generation functions"""
    
    @pytest.fixture
    def sample_state(self):
        """Sample state for basic generation"""
        return {
            "settings": {"output_format": "markdown"},
            "class_info": {
                "subject": "Test Meeting",
                "date": "2023-01-15",
                "period": "1限"
            }
        }

    def test_generate_basic_minutes_success(self, sample_state):
        """Test successful basic minutes generation"""
        transcription = "Speaker 1: Hello everyone. Speaker 2: Thank you for joining."
        
        result = _generate_basic_minutes(transcription, sample_state)
        
        assert isinstance(result, str)
        assert "# 議事録" in result
        assert "Test Meeting" in result
        assert "2023-01-15" in result
        assert "Speaker 1:" in result
        assert "Speaker 2:" in result

    def test_generate_basic_summary_success(self):
        """Test successful basic summary generation"""
        transcription = """
        Speaker 1: We need to discuss the project timeline.
        Speaker 2: The deadline is next month.
        Speaker 1: We should prioritize the critical features.
        Speaker 2: Agreed. Let's focus on core functionality.
        """
        
        result = _generate_basic_summary(transcription)
        
        assert isinstance(result, str)
        assert "## 要約" in result
        assert len(result) > 0

    def test_generate_basic_minutes_empty_transcription(self, sample_state):
        """Test basic minutes generation with empty transcription"""
        result = _generate_basic_minutes("", sample_state)
        
        assert isinstance(result, str)
        assert "# 議事録" in result
        assert "内容なし" in result or "No content" in result.lower()

    def test_generate_basic_minutes_missing_class_info(self, sample_state):
        """Test basic minutes generation with missing class info"""
        del sample_state["class_info"]
        
        result = _generate_basic_minutes("Test transcription", sample_state)
        
        assert isinstance(result, str)
        assert "# 議事録" in result


class TestPromptBuilding:
    """Tests for prompt building functions"""
    
    @pytest.fixture
    def sample_state(self):
        """Sample state for prompt building"""
        return {
            "class_info": {
                "subject": "Project Meeting",
                "date": "2023-01-15",
                "period": "1限"
            },
            "settings": {"output_format": "markdown"}
        }

    @patch('src.workflows.nodes.minutes_generation._load_minutes_prompt')
    def test_build_minutes_prompt_success(self, mock_load_prompt, sample_state):
        """Test successful minutes prompt building"""
        mock_load_prompt.return_value = "Generate minutes for {subject} on {date}: {transcription}"
        
        result = _build_minutes_prompt("test transcription", sample_state)
        
        assert isinstance(result, str)
        assert "Project Meeting" in result
        assert "2023-01-15" in result
        assert "test transcription" in result

    @patch('src.workflows.nodes.minutes_generation._load_summary_prompt')
    def test_build_summary_prompt_success(self, mock_load_prompt, sample_state):
        """Test successful summary prompt building"""
        mock_load_prompt.return_value = "Summarize {subject} meeting: {transcription}"
        
        result = _build_summary_prompt("test transcription", sample_state)
        
        assert isinstance(result, str)
        assert "Project Meeting" in result
        assert "test transcription" in result

    def test_build_minutes_prompt_missing_class_info(self):
        """Test minutes prompt building with missing class info"""
        state = {"settings": {"output_format": "markdown"}}
        
        with patch('src.workflows.nodes.minutes_generation._load_minutes_prompt') as mock_load:
            mock_load.return_value = "Generate minutes: {transcription}"
            
            result = _build_minutes_prompt("test transcription", state)
            
            assert isinstance(result, str)
            assert "test transcription" in result


class TestPromptLoading:
    """Tests for prompt loading functions"""

    @patch('builtins.open', mock_open(read_data="Test minutes prompt template"))
    @patch('os.path.exists', return_value=True)
    def test_load_minutes_prompt_success(self, mock_exists):
        """Test successful minutes prompt loading"""
        result = _load_minutes_prompt()
        
        assert result == "Test minutes prompt template"

    @patch('os.path.exists', return_value=False)
    def test_load_minutes_prompt_file_not_found(self, mock_exists):
        """Test minutes prompt loading with missing file"""
        result = _load_minutes_prompt()
        
        assert isinstance(result, str)
        assert len(result) > 0  # Should return default prompt

    @patch('builtins.open', mock_open(read_data="Test summary prompt template"))
    @patch('os.path.exists', return_value=True)
    def test_load_summary_prompt_success(self, mock_exists):
        """Test successful summary prompt loading"""
        result = _load_summary_prompt()
        
        assert result == "Test summary prompt template"

    @patch('builtins.open', side_effect=IOError("Permission denied"))
    @patch('os.path.exists', return_value=True)
    def test_load_minutes_prompt_read_error(self, mock_exists, mock_open_error):
        """Test minutes prompt loading with read error"""
        result = _load_minutes_prompt()
        
        assert isinstance(result, str)
        assert len(result) > 0  # Should return default prompt


class TestContentFormatting:
    """Tests for content formatting functions"""

    def test_format_transcription_content_basic(self):
        """Test basic transcription content formatting"""
        transcription = "Speaker 1: Hello. Speaker 2: Hi there."
        
        result = _format_transcription_content(transcription)
        
        assert isinstance(result, str)
        assert "Speaker 1:" in result
        assert "Speaker 2:" in result

    def test_format_transcription_content_with_timestamps(self):
        """Test transcription formatting with timestamps"""
        transcription = "[00:01:30] Speaker 1: Hello. [00:02:15] Speaker 2: Hi there."
        
        result = _format_transcription_content(transcription)
        
        assert isinstance(result, str)
        assert "Speaker 1:" in result
        assert "Speaker 2:" in result

    def test_format_transcription_content_empty(self):
        """Test transcription formatting with empty content"""
        result = _format_transcription_content("")
        
        assert result == ""

    def test_format_transcription_content_cleanup(self):
        """Test transcription formatting with cleanup"""
        transcription = "  Speaker 1:   Hello world.   \n\n  Speaker 2:  Hi there.  "
        
        result = _format_transcription_content(transcription)
        
        assert isinstance(result, str)
        assert "  " not in result  # Should remove extra spaces
        assert result.strip() == result  # Should be trimmed


class TestPostProcessing:
    """Tests for post-processing functions"""
    
    @pytest.fixture
    def sample_state(self):
        """Sample state for post-processing"""
        return {
            "settings": {"output_format": "markdown"},
            "class_info": {"subject": "Test Meeting"}
        }

    def test_post_process_minutes_basic(self, sample_state):
        """Test basic minutes post-processing"""
        minutes = "# Meeting Minutes\n\nContent here."
        
        result = _post_process_minutes(minutes, sample_state)
        
        assert isinstance(result, str)
        assert "Meeting Minutes" in result

    def test_post_process_minutes_with_conversion(self, sample_state):
        """Test minutes post-processing with format conversion"""
        sample_state["settings"]["output_format"] = "html"
        minutes = "# Meeting Minutes\n\nContent here."
        
        with patch('src.workflows.nodes.minutes_generation._convert_format') as mock_convert:
            mock_convert.return_value = "<h1>Meeting Minutes</h1><p>Content here.</p>"
            
            result = _post_process_minutes(minutes, sample_state)
            
            assert "<h1>" in result
            mock_convert.assert_called_once_with(minutes, "html")

    @pytest.mark.parametrize("input_format,output_format", [
        ("markdown", "html"),
        ("markdown", "text"),
        ("html", "markdown"),
        ("text", "markdown"),
    ])
    def test_convert_format_various(self, input_format, output_format):
        """Test format conversion between various formats"""
        content = "# Test Content\n\nThis is a test."
        
        result = _convert_format(content, output_format)
        
        assert isinstance(result, str)
        assert len(result) > 0

    def test_convert_format_unsupported(self):
        """Test format conversion with unsupported format"""
        content = "Test content"
        
        result = _convert_format(content, "unsupported_format")
        
        assert result == content  # Should return original content


class TestUtilityFunctions:
    """Tests for utility functions"""

    def test_extract_key_points_basic(self):
        """Test basic key points extraction"""
        minutes = """
        # Meeting Minutes
        
        ## Key Points
        - Important decision made
        - Action item assigned
        - Deadline set for next week
        
        ## Discussion
        We talked about various topics.
        """
        
        result = extract_key_points(minutes)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert any("decision" in point.lower() for point in result)

    def test_extract_key_points_no_points(self):
        """Test key points extraction with no clear points"""
        minutes = "This is just regular text without clear key points."
        
        result = extract_key_points(minutes)
        
        assert isinstance(result, list)
        # Should still return something, even if empty

    def test_generate_title_from_content_with_class_info(self):
        """Test title generation with class info"""
        transcription = "We discussed the quarterly budget and project timeline."
        class_info = {
            "subject": "Budget Meeting",
            "date": "2023-01-15",
            "period": "1限"
        }
        
        result = generate_title_from_content(transcription, class_info)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Budget Meeting" in result or "budget" in result.lower()

    def test_generate_title_from_content_without_class_info(self):
        """Test title generation without class info"""
        transcription = "We discussed the quarterly budget and project timeline."
        
        result = generate_title_from_content(transcription)
        
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_title_from_content_empty_transcription(self):
        """Test title generation with empty transcription"""
        result = generate_title_from_content("")
        
        assert isinstance(result, str)
        assert len(result) > 0  # Should return default title

    def test_generate_title_from_content_long_transcription(self):
        """Test title generation with very long transcription"""
        long_transcription = "This is a very long transcription. " * 100
        
        result = generate_title_from_content(long_transcription)
        
        assert isinstance(result, str)
        assert len(result) < 200  # Should be reasonably short title