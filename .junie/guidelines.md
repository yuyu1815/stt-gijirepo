# STT Meeting Minutes System Development Guidelines - LangGraph Migration Version

## 1. Project Overview

### 1.1 System Purpose
Migrate a system that automatically generates high-quality meeting minutes from audio and video files to a LangGraph-based workflow system, improving maintainability, extensibility, and debuggability.

### 1.2 Key Features
- Automatic detection and preprocessing of audio/video files
- High-precision transcription using Gemini API
- AI-powered meeting minutes generation and quality checking
- Automatic upload with Notion integration
- Structured workflow management using LangGraph

## 2. Build and Setup Procedures

### 2.1 Environment Requirements
- **Python**: 3.8 or higher (recommended: 3.11+)
- **FFmpeg**: Required for audio/video processing
- **Git**: Version control
- **Virtual Environment**: venv or conda recommended

### 2.2 Initial Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd stt-gijirepo

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# 3. Install dependencies (development environment)
make install-dev
# or manually
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black isort mypy flake8 pre-commit

# 4. Development environment setup
make setup
# This executes the following:
# - Create .env file (copy from .env.example)
# - Create directories (logs, temp, output)
# - Setup pre-commit hooks
```

### 2.3 Environment Variables Configuration
Edit the `.env` file to set required API keys:
```bash
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Notion API (optional)
NOTION_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=your_database_id_here
```

### 2.4 Configuration Verification
```bash
# Environment setup check
make check-env

# Dependency verification
pip list | grep -E "(langgraph|google-genai|notion-client|pytest)"
```

### 2.5 Build and Packaging
```bash
# Package build
make build

# Cleanup
make clean

# Complete cleanup (including config files)
make clean-all
```

## 2. Architecture Principles

### 2.1 LangGraph-Based Design
- **Node-Based Processing**: Implement each function as independent nodes
- **State Management**: Type-safe state management using TypedDict
- **Conditional Branching**: Workflow control through clear conditional branching logic
- **Error Handling**: Unified error handling and retry functionality

### 2.2 Code Structure
```
stt-gijirepo/
├── workflows/           # LangGraph workflow definitions
│   ├── __init__.py
│   ├── stt_workflow.py  # Main workflow
│   └── nodes/           # Individual node implementations
├── core/                # Core functionality
│   ├── audio_processing.py
│   ├── video_processing.py
│   └── ai_services.py
├── utils/               # Utilities
└── tests/               # Test code
```

## 3. Development Conventions

### 3.1 Coding Conventions
- Use **Python 3.8+**
- **Type Hints** are mandatory
- **Docstrings** written in Google style
- Code formatting with **Black**
- Import organization with **isort**

### 3.2 Node Implementation Conventions
```python
def node_function(state: STTState) -> STTState:
    """
    Standard template for node functions
    
    Args:
        state: Current processing state
        
    Returns:
        Updated processing state
    """
    try:
        # Processing logic
        state["processing_log"].append("Processing completed message")
        return state
    except Exception as e:
        state["errors"].append(f"Error message: {str(e)}")
        return state
```

### 3.3 State Management Conventions
```python
class STTState(TypedDict):
    # Input information
    file_path: str
    settings: dict
    
    # Processing state
    file_type: Optional[str]
    is_video_dark: Optional[bool]
    audio_duration: Optional[float]
    chunks: Optional[List[str]]
    
    # Processing results
    transcription: Optional[str]
    quality_check_result: Optional[dict]
    minutes: Optional[str]
    class_info: Optional[dict]
    
    # Errors and logs
    errors: List[str]
    processing_log: List[str]
    
    # Settings
    upload_to_notion: bool
    notion_database_id: Optional[str]
```

## 4. Workflow Design

### 4.1 Main Workflow
1. **file_analysis**: File analysis and type determination
2. **video_processing**: Video preprocessing (when needed)
3. **audio_splitting**: Audio splitting (for long audio)
4. **transcription**: Transcription processing
5. **quality_check**: Quality check
6. **minutes_generation**: Meeting minutes generation
7. **notion_upload**: Notion upload (optional)

### 4.2 Conditional Branching Rules
- **File Type**: Video → preprocessing, Audio → direct processing
- **Video Brightness**: Dark → audio extraction, Bright → direct processing
- **Audio Length**: Over 40 minutes → split processing, Under → direct processing
- **Error Occurrence**: Transition to error node

## 5. Error Handling

### 5.1 Error Classification
- **Input Errors**: Invalid files, unsupported formats
- **Processing Errors**: API call failures, conversion errors
- **Output Errors**: Save failures, upload failures

### 5.2 Retry Strategy
```python
def with_retry(func, max_retries: int = 5, backoff_factor: float = 2.0):
    """Retry functionality with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(backoff_factor ** attempt)
```

## 6. Test Setup and Execution

### 6.1 Test Environment Setup
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# or install development environment all at once
make install-dev
```

### 6.2 Test Execution Commands
```bash
# Basic test execution
make test
# or
python -m pytest src/tests/ -v

# Test with coverage
make test-coverage
# or
python -m pytest src/tests/ --cov=src --cov-report=html --cov-report=term-missing

# Unit tests only
make test-unit
python -m pytest src/tests/test_core/ src/tests/test_utils/ -v

# Integration tests only
make test-integration
python -m pytest src/tests/test_workflows/ -v

# Execute specific test file
python -m pytest src/tests/test_core/test_ai_services.py -v

# Execute specific test method
python -m pytest src/tests/test_core/test_ai_services.py::TestGeminiService::test_init_success -v
```

### 6.3 Test Classification and Markers
```bash
# Execute only fast tests (exclude slow markers)
python -m pytest -m "not slow"

# Execute only integration tests
python -m pytest -m integration

# Exclude API-required tests
python -m pytest -m "not requires_api"
```

### 6.4 Test Creation Examples

#### Basic Test Structure
```python
import pytest
from src.utils.class_info import extract_class_period

class TestClassInfo:
    """Tests for ClassInfo functionality"""
    
    def test_extract_class_period_basic(self):
        """Basic class period extraction test"""
        # 1st period (50 minutes = 0:50)
        result = extract_class_period(50)
        assert result == "1限"
        
        # 2nd period (140 minutes = 2:20)
        result = extract_class_period(140)
        assert result == "2限"
    
    @pytest.mark.parametrize("minutes,expected", [
        (50, "1限"),
        (140, "2限"),
        (230, "3限"),
        (320, "4限"),
    ])
    def test_extract_class_period_parametrized(self, minutes, expected):
        """Parametrized test"""
        assert extract_class_period(minutes) == expected
```

#### Tests Using Mocks
```python
import pytest
from unittest.mock import Mock, patch
from src.core.ai_services import GeminiService

class TestGeminiService:
    """Tests for GeminiService"""
    
    @patch('google.genai.configure')
    @patch('google.genai.GenerativeModel')
    def test_transcribe_audio_success(self, mock_model_class, mock_configure):
        """Audio transcription success test"""
        # Mock setup
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Test transcription result"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        # Test execution
        service = GeminiService(api_key="test_key")
        result = service.transcribe_audio("test_audio.wav")
        
        # Verification
        assert result == "Test transcription result"
```

#### Tests Using Fixtures
```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_audio_file(tmp_path):
    """Test audio file"""
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake_audio_data")
    return audio_file

def test_audio_processing(sample_audio_file):
    """Audio processing test"""
    assert sample_audio_file.exists()
    assert sample_audio_file.suffix == ".wav"
```

### 6.5 Test Configuration Files

#### pytest Configuration (pyproject.toml)
```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
]
testpaths = ["src/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

### 6.6 Coverage Reports
```bash
# Generate HTML coverage report
make test-coverage

# View coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### 6.7 Continuous Testing
```bash
# Auto-run tests on file changes
make test-watch
# or
python -m pytest src/tests/ -f
```

## 7. Performance Optimization

### 7.1 Parallel Processing
- Parallelization of audio splitting processing
- Parallelization of multiple file processing
- Efficient API calls

### 7.2 Memory Management
- Streaming processing of large files
- Proper deletion of intermediate files
- Memory usage monitoring

## 8. Monitoring and Logging

### 8.1 Log Levels
- **DEBUG**: Detailed processing information
- **INFO**: General processing status
- **WARNING**: Situations requiring attention
- **ERROR**: Error information

### 8.2 Monitoring Items
- Processing time measurement
- API call count
- Memory usage
- Error occurrence rate

## 9. Security

### 9.1 API Key Management
- Management through environment variables
- Configuration file encryption
- Access permission restrictions

### 9.2 File Processing
- Input file validation
- Safe deletion of temporary files
- Prevention of path traversal attacks

## 10. Migration Plan

### 10.1 Phase 1: Foundation Building (1-2 weeks)
- LangGraph environment setup
- Basic state class definition
- Core node implementation

### 10.2 Phase 2: Main Feature Migration (2-3 weeks)
- AI processing node implementation
- Meeting minutes generation workflow construction
- Quality check feature integration

### 10.3 Phase 3: Advanced Feature Implementation (2-3 weeks)
- Notion integration improvement
- Monitoring and debugging feature addition
- Batch processing feature implementation

### 10.4 Phase 4: Optimization and Testing (1-2 weeks)
- Performance optimization
- Comprehensive test execution
- Documentation preparation

## 11. Quality Assurance

### 11.1 Code Review
- Mandatory review for all PRs
- Design review for architecture changes
- Include security perspective reviews

### 11.2 Continuous Integration
- Automated test execution
- Code quality checks
- Security scanning

## 12. Documentation Management

### 12.1 Required Documentation
- API specifications
- Workflow diagrams
- Operation procedures
- Troubleshooting guides

### 12.2 Update Rules
- Synchronous documentation updates with code changes
- Regular documentation reviews
- Integration with version control

## 13. Operations and Maintenance

### 13.1 Deployment
- Gradual deployment
- Rollback procedure establishment
- Configuration management automation

### 13.2 Monitoring and Alerts
- System operation status monitoring
- Error rate monitoring
- Performance degradation detection

## 14. Development-Specific Information

### 14.1 Project-Specific Code Conventions

#### File Naming Rules
```
# Workflow nodes
src/workflows/nodes/{function_name}.py

# Prompt definitions
src/prompts/definitions/{category}/{specific_function}.md

# Test files
src/tests/test_{module_name}/test_{function_name}.py
```

#### Import Order (isort compliant)
```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party libraries
import pytest
from google import genai
from langgraph import StateGraph

# 3. Local imports
from src.core.ai_services import GeminiService
from src.utils.logging_config import get_logger
```

#### Log Output Patterns
```python
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def example_function():
    logger.info("Processing started: example_function")
    try:
        # Processing logic
        logger.debug("Detailed processing information")
        result = some_operation()
        logger.info(f"Processing completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        raise
```

### 14.2 Debugging and Troubleshooting

#### Common Issues and Solutions

**1. Gemini API Errors**
```bash
# Check API key
make check-env

# Check logs
tail -f logs/stt_*.log | grep -i error

# Test API connection
python -c "from src.core.ai_services import GeminiService; print('API OK')"
```

**2. Audio/Video Processing Errors**
```bash
# Check FFmpeg installation
ffmpeg -version

# Check test media files
ls -la test_media/

# Test audio processing
python -c "from src.core.audio_processing import AudioProcessor; print('Audio OK')"
```

**3. Test Failure Handling**
```bash
# Detailed test output
python -m pytest src/tests/ -v -s --tb=long

# Execute specific test only
python -m pytest src/tests/test_core/test_ai_services.py::TestGeminiService::test_init_success -v

# Check coverage
make test-coverage
open htmlcov/index.html
```

#### Performance Monitoring
```python
from src.utils.performance_monitor import PerformanceMonitor

# Usage example
monitor = PerformanceMonitor()
monitor.start_monitoring()

# Execute processing
result = some_heavy_operation()

metrics = monitor.get_metrics()
print(f"CPU usage: {metrics['cpu_percent']}%")
print(f"Memory usage: {metrics['memory_mb']}MB")
```

### 14.3 Development Workflow

#### New Feature Development Procedure
1. **Create branch**: `git checkout -b feature/new-feature`
2. **Create tests**: Write tests first (TDD recommended)
3. **Implementation**: Feature implementation
4. **Quality check**: `make quality-check`
5. **Run tests**: `make test-coverage`
6. **Pull request**: Request review

#### Commit Conventions
```
feat: Add new feature
fix: Bug fix
docs: Documentation update
style: Code style fix
refactor: Refactoring
test: Add/modify tests
chore: Other changes
```

### 14.4 Project-Specific Settings

#### Environment Variables List
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key

# Optional
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
LOG_LEVEL=INFO
MAX_AUDIO_DURATION=3600
CHUNK_SIZE=300
```

#### Configuration File (settings.json)
```json
{
  "audio_settings": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_duration": 300
  },
  "ai_settings": {
    "model_name": "gemini-1.5-pro",
    "max_retries": 3,
    "timeout": 60
  },
  "output_settings": {
    "format": "markdown",
    "include_timestamps": true,
    "include_confidence": false
  }
}
```

### 14.5 Frequently Used Make Commands

```bash
# Development environment setup
make setup

# Test execution (recommended)
make test-coverage

# Code quality check
make quality-check

# Execute (sample file)
make run FILE=test_media/test.mp3

# Batch processing
make run-batch DIR=input_directory

# Log monitoring
make logs

# Environment check
make check-env

# Cleanup
make clean
```

### 14.6 IDE Configuration Recommendations

#### VS Code Settings (.vscode/settings.json)
```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/htmlcov": true
  }
}
```

#### PyCharm Settings
- Interpreter: `.venv/bin/python`
- Code style: Black (100 characters)
- Import optimization: isort
- Test runner: pytest

By following these guidelines, we aim to build a maintainable and extensible STT meeting minutes system.