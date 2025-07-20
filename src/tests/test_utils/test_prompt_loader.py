"""
プロンプトローダーのテストコード
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from src.utils.prompt_loader import (
    PromptLoader,
    PromptTemplate,
    load_and_render_prompt,
    get_prompt_loader
)


class TestPromptTemplate:
    """PromptTemplateクラスのテスト"""
    
    def test_prompt_template_creation(self):
        """プロンプトテンプレートの作成テスト"""
        template = PromptTemplate(
            name="test_prompt",
            overview="テスト用プロンプト",
            parameters={"param1": "パラメータ1の説明"},
            content="これは{param1}のテストです。",
            examples="使用例",
            notes="注意事項"
        )
        
        assert template.name == "test_prompt"
        assert template.overview == "テスト用プロンプト"
        assert template.parameters == {"param1": "パラメータ1の説明"}
        assert template.content == "これは{param1}のテストです。"
        assert template.examples == "使用例"
        assert template.notes == "注意事項"


class TestPromptLoader:
    """PromptLoaderクラスのテスト"""
    
    @pytest.fixture
    def temp_prompts_dir(self):
        """テスト用の一時プロンプトディレクトリを作成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            # テスト用のカテゴリディレクトリを作成
            transcription_dir = prompts_dir / "transcription"
            transcription_dir.mkdir()
            
            # テスト用のプロンプトファイルを作成
            test_prompt_content = """# テスト文字起こしプロンプト

## 概要
テスト用の文字起こしプロンプトです。

## パラメータ
- `{language}`: 言語コード（例: "ja", "en"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の音声ファイルを{language}で文字起こししてください。

**言語**: {language}

{custom_instructions}

## 使用例
```
言語: ja
出力: 日本語での文字起こし
```

## 注意事項
- 正確性を重視してください
- 不明瞭な部分は[不明瞭]と記載してください
"""
            
            test_prompt_file = transcription_dir / "test_transcription.md"
            test_prompt_file.write_text(test_prompt_content, encoding='utf-8')
            
            yield str(prompts_dir)
    
    def test_prompt_loader_initialization(self, temp_prompts_dir):
        """プロンプトローダーの初期化テスト"""
        loader = PromptLoader(temp_prompts_dir)
        assert loader.prompts_dir == Path(temp_prompts_dir)
        assert loader._cache == {}
    
    def test_load_prompt_success(self, temp_prompts_dir):
        """プロンプト読み込み成功テスト"""
        loader = PromptLoader(temp_prompts_dir)
        template = loader.load_prompt("transcription", "test_transcription")
        
        assert template.name == "test_transcription"
        assert template.overview == "テスト用の文字起こしプロンプトです。"
        assert "language" in template.parameters
        assert "custom_instructions" in template.parameters
        assert "{language}" in template.content
        assert template.examples is not None
        assert template.notes is not None
    
    def test_load_prompt_file_not_found(self, temp_prompts_dir):
        """存在しないプロンプトファイルの読み込みテスト"""
        loader = PromptLoader(temp_prompts_dir)
        
        with pytest.raises(FileNotFoundError):
            loader.load_prompt("transcription", "nonexistent_prompt")
    
    def test_load_prompt_caching(self, temp_prompts_dir):
        """プロンプトキャッシュ機能のテスト"""
        loader = PromptLoader(temp_prompts_dir)
        
        # 初回読み込み
        template1 = loader.load_prompt("transcription", "test_transcription")
        
        # 2回目読み込み（キャッシュから）
        template2 = loader.load_prompt("transcription", "test_transcription")
        
        # 同じオブジェクトが返されることを確認
        assert template1 is template2
        assert len(loader._cache) == 1
    
    def test_render_prompt(self, temp_prompts_dir):
        """プロンプトレンダリングテスト"""
        loader = PromptLoader(temp_prompts_dir)
        template = loader.load_prompt("transcription", "test_transcription")
        
        rendered = loader.render_prompt(
            template,
            language="ja",
            custom_instructions="追加の指示です"
        )
        
        assert "ja" in rendered
        assert "追加の指示です" in rendered
        assert "{language}" not in rendered
        assert "{custom_instructions}" not in rendered
    
    def test_render_prompt_with_none_values(self, temp_prompts_dir):
        """None値を含むプロンプトレンダリングテスト"""
        loader = PromptLoader(temp_prompts_dir)
        template = loader.load_prompt("transcription", "test_transcription")
        
        rendered = loader.render_prompt(
            template,
            language="en",
            custom_instructions=None
        )
        
        assert "en" in rendered
        assert "{language}" not in rendered
        assert "{custom_instructions}" not in rendered
    
    def test_get_available_prompts(self, temp_prompts_dir):
        """利用可能プロンプト一覧取得テスト"""
        loader = PromptLoader(temp_prompts_dir)
        available = loader.get_available_prompts()
        
        assert "transcription" in available
        assert "test_transcription" in available["transcription"]
    
    def test_clear_cache(self, temp_prompts_dir):
        """キャッシュクリアテスト"""
        loader = PromptLoader(temp_prompts_dir)
        
        # プロンプトを読み込んでキャッシュに保存
        loader.load_prompt("transcription", "test_transcription")
        assert len(loader._cache) == 1
        
        # キャッシュをクリア
        loader.clear_cache()
        assert len(loader._cache) == 0
    
    def test_parse_markdown_missing_required_section(self, temp_prompts_dir):
        """必須セクションが欠けているMarkdownの解析テスト"""
        loader = PromptLoader(temp_prompts_dir)
        
        # 概要セクションが欠けているMarkdown
        invalid_content = """# テストプロンプト

## パラメータ
- `{param}`: パラメータ

## プロンプト本文
テスト内容
"""
        
        with pytest.raises(ValueError, match="Missing required section '概要'"):
            loader._parse_markdown(invalid_content, "test_prompt")
    
    def test_parse_parameters(self, temp_prompts_dir):
        """パラメータ解析テスト"""
        loader = PromptLoader(temp_prompts_dir)
        
        param_section = """- `{language}`: 言語コード（例: "ja", "en"）
- `{custom_instructions}`: カスタム指示（オプション）
- `{quality}`: 品質レベル"""
        
        parameters = loader._parse_parameters(param_section)
        
        assert len(parameters) == 3
        assert "language" in parameters
        assert "custom_instructions" in parameters
        assert "quality" in parameters
        assert "言語コード" in parameters["language"]


class TestConvenienceFunctions:
    """便利関数のテスト"""
    
    @pytest.fixture
    def temp_prompts_dir(self):
        """テスト用の一時プロンプトディレクトリを作成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            # テスト用のカテゴリディレクトリを作成
            test_dir = prompts_dir / "test_category"
            test_dir.mkdir()
            
            # テスト用のプロンプトファイルを作成
            test_prompt_content = """# テストプロンプト

## 概要
テスト用プロンプト

## パラメータ
- `{message}`: メッセージ

## プロンプト本文
メッセージ: {message}
"""
            
            test_prompt_file = test_dir / "test_prompt.md"
            test_prompt_file.write_text(test_prompt_content, encoding='utf-8')
            
            yield str(prompts_dir)
    
    @patch('src.utils.prompt_loader.PromptLoader')
    def test_load_and_render_prompt(self, mock_loader_class, temp_prompts_dir):
        """load_and_render_prompt関数のテスト"""
        # モックの設定
        mock_loader = mock_loader_class.return_value
        mock_template = PromptTemplate(
            name="test_prompt",
            overview="テスト",
            parameters={"message": "メッセージ"},
            content="メッセージ: {message}"
        )
        mock_loader.load_prompt.return_value = mock_template
        mock_loader.render_prompt.return_value = "メッセージ: こんにちは"
        
        # 関数を実行
        result = load_and_render_prompt(
            category="test_category",
            prompt_name="test_prompt",
            message="こんにちは"
        )
        
        # 結果を確認
        assert result == "メッセージ: こんにちは"
        mock_loader.load_prompt.assert_called_once_with("test_category", "test_prompt")
        mock_loader.render_prompt.assert_called_once_with(mock_template, message="こんにちは")
    
    def test_get_prompt_loader_singleton(self):
        """get_prompt_loader関数のシングルトンテスト"""
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()
        
        # 同じインスタンスが返されることを確認
        assert loader1 is loader2


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    def test_invalid_prompts_directory(self):
        """存在しないプロンプトディレクトリの処理テスト"""
        loader = PromptLoader("/nonexistent/directory")
        available = loader.get_available_prompts()
        
        # 空の辞書が返されることを確認
        assert available == {}
    
    @pytest.fixture
    def temp_prompts_dir_with_invalid_file(self):
        """不正なプロンプトファイルを含む一時ディレクトリを作成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            test_dir = prompts_dir / "test_category"
            test_dir.mkdir()
            
            # 不正なプロンプトファイル（プロンプト本文セクションなし）
            invalid_content = """# 不正なプロンプト

## 概要
これは不正なプロンプトです

## パラメータ
- `{param}`: パラメータ
"""
            
            invalid_file = test_dir / "invalid_prompt.md"
            invalid_file.write_text(invalid_content, encoding='utf-8')
            
            yield str(prompts_dir)
    
    def test_load_invalid_prompt_file(self, temp_prompts_dir_with_invalid_file):
        """不正なプロンプトファイルの読み込みテスト"""
        loader = PromptLoader(temp_prompts_dir_with_invalid_file)
        
        with pytest.raises(ValueError, match="Missing required section 'プロンプト本文'"):
            loader.load_prompt("test_category", "invalid_prompt")