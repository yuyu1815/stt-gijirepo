"""
統合プロンプト管理システムのテスト

このモジュールでは、統合プロンプトファイル（base_prompts.md, school_prompts.md, meeting_prompts.md, override_prompts.md）
からプロンプトを読み込む機能をテストします。
"""

import os
import pytest
from pathlib import Path
import tempfile
import shutil

from src.utils.prompt_loader import PromptLoader, load_and_render_prompt, get_prompt_loader


class TestConsolidatedPromptLoader:
    """統合プロンプト管理システムのテストクラス"""

    @pytest.fixture
    def temp_prompts_dir(self):
        """テスト用の一時プロンプトディレクトリを作成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 統合プロンプトファイルを作成
            self._create_base_prompts_file(temp_path)
            self._create_school_prompts_file(temp_path)
            self._create_override_prompts_file(temp_path)
            
            # 従来の個別ファイル用のディレクトリ構造を作成
            legacy_dir = temp_path / "transcription"
            legacy_dir.mkdir(exist_ok=True)
            self._create_legacy_prompt_file(legacy_dir)
            
            yield temp_path
    
    def _create_base_prompts_file(self, dir_path):
        """base_prompts.mdファイルを作成"""
        content = """# 基本プロンプト定義ファイル

このファイルには、一般的・汎用的なプロンプトが含まれています。

---

<transcription_basic_transcription>
# 基本文字起こしプロンプト

## 概要
音声ファイルから基本的な文字起こしを行うためのプロンプトです。

## パラメータ
- `{language}`: 音声の言語（例: "ja", "en"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の音声ファイルを正確に文字起こししてください。

**言語**: {language}

**指示事項**:
- 話者が複数いる場合は、話者を区別してください
- 専門用語や固有名詞も正確に書き起こしてください

{custom_instructions}
</transcription_basic_transcription>

---

<quality_check_basic_check>
# 基本品質チェックプロンプト

## 概要
文字起こし結果の品質をチェックするためのプロンプトです。

## パラメータ
- `{content}`: チェック対象のテキスト
- `{language}`: 対象言語（例: "ja", "en"）

## プロンプト本文

以下の文字起こし結果の品質をチェックしてください。

**言語**: {language}

**チェック項目**:
- 文法的な正確さ
- 内容の一貫性
- 専門用語の正確さ

**文字起こし結果**:
{content}
</quality_check_basic_check>
"""
        with open(dir_path / "base_prompts.md", "w", encoding="utf-8") as f:
            f.write(content)
    
    def _create_school_prompts_file(self, dir_path):
        """school_prompts.mdファイルを作成"""
        content = """# 学校・教育関連プロンプト定義ファイル

このファイルには、授業・講義関連のプロンプトが含まれています。

---

<minutes_generation_lecture_notes>
# 講義ノート生成プロンプト

## 概要
講義の文字起こしから教育的な講義ノートを生成するためのプロンプトです。

## パラメータ
- `{transcription}`: 講義の文字起こし結果
- `{lecture_info}`: 講義情報（科目名、講師名など）
- `{language}`: 出力言語（例: "ja", "en"）

## プロンプト本文

以下の講義の文字起こしから、教育的な講義ノートを作成してください。

**言語**: {language}
**講義情報**: {lecture_info}

**講義ノート作成指示**:
- 重要なポイントを箇条書きでまとめてください
- 専門用語には簡潔な説明を付けてください
- 例題や演習問題も含めてください

**文字起こし結果**:
{transcription}
</minutes_generation_lecture_notes>
"""
        with open(dir_path / "school_prompts.md", "w", encoding="utf-8") as f:
            f.write(content)
    
    def _create_override_prompts_file(self, dir_path):
        """override_prompts.mdファイルを作成"""
        content = """# オーバーライドプロンプト定義ファイル

このファイルには、他のプロンプト定義ファイルで定義されたプロンプトを上書きするためのプロンプトが含まれています。

---

<transcription_basic_transcription>
# 基本文字起こしプロンプト（オーバーライド版）

## 概要
音声ファイルから基本的な文字起こしを行うためのカスタマイズされたプロンプトです。

## パラメータ
- `{language}`: 音声の言語（例: "ja", "en"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の音声ファイルを高品質で文字起こししてください。

**言語**: {language}

**オーバーライド指示事項**:
- 話者が複数いる場合は、声の特徴から話者を区別してください
- すべての発言を漏れなく記録してください
- 専門用語や固有名詞は正確に書き起こしてください
- 音声が不明瞭な場合は[不明瞭]と記載してください

{custom_instructions}
</transcription_basic_transcription>
"""
        with open(dir_path / "override_prompts.md", "w", encoding="utf-8") as f:
            f.write(content)
    
    def _create_legacy_prompt_file(self, dir_path):
        """従来の個別プロンプトファイルを作成"""
        content = """# レガシー文字起こしプロンプト

## 概要
従来の方式で定義された文字起こしプロンプトです。

## パラメータ
- `{language}`: 音声の言語（例: "ja", "en"）

## プロンプト本文

以下の音声を文字起こししてください。

**言語**: {language}

**指示事項**:
- これは従来の個別ファイル方式で定義されたプロンプトです
"""
        with open(dir_path / "legacy_transcription.md", "w", encoding="utf-8") as f:
            f.write(content)
    
    def test_load_from_base_prompts(self, temp_prompts_dir):
        """base_prompts.mdからプロンプトを読み込めることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        template = loader.load_prompt("quality_check", "basic_check")
        
        assert template.name == "basic_check"
        assert "文字起こし結果の品質をチェックするためのプロンプト" in template.overview
        assert "language" in template.parameters
        assert "content" in template.parameters
        assert "文字起こし結果の品質をチェックしてください" in template.content
    
    def test_load_from_school_prompts(self, temp_prompts_dir):
        """school_prompts.mdからプロンプトを読み込めることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        template = loader.load_prompt("minutes_generation", "lecture_notes")
        
        assert template.name == "lecture_notes"
        assert "講義の文字起こしから教育的な講義ノートを生成する" in template.overview
        assert "transcription" in template.parameters
        assert "lecture_info" in template.parameters
        assert "language" in template.parameters
        assert "教育的な講義ノートを作成してください" in template.content
    
    def test_override_mechanism(self, temp_prompts_dir):
        """override_prompts.mdのプロンプトが優先されることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        template = loader.load_prompt("transcription", "basic_transcription")
        
        assert template.name == "basic_transcription"
        assert "カスタマイズされたプロンプト" in template.overview
        assert "オーバーライド指示事項" in template.content
        assert "高品質で文字起こし" in template.content
    
    def test_legacy_file_support(self, temp_prompts_dir):
        """従来の個別ファイル方式もサポートしていることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        template = loader.load_prompt("transcription", "legacy_transcription")
        
        assert template.name == "legacy_transcription"
        assert "従来の方式で定義された文字起こしプロンプト" in template.overview
        assert "language" in template.parameters
        assert "これは従来の個別ファイル方式で定義されたプロンプト" in template.content
    
    def test_render_prompt(self, temp_prompts_dir):
        """プロンプトのレンダリングが正しく行われることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        template = loader.load_prompt("quality_check", "basic_check")
        
        rendered = loader.render_prompt(
            template,
            language="日本語",
            content="これはテスト用の文字起こし結果です。"
        )
        
        assert "**言語**: 日本語" in rendered
        assert "**文字起こし結果**:\nこれはテスト用の文字起こし結果です。" in rendered
    
    def test_convenience_function(self, temp_prompts_dir):
        """便利関数 load_and_render_prompt が正しく動作することを確認"""
        # モンキーパッチでグローバルローダーを一時的に置き換え
        import src.utils.prompt_loader
        original_loader = src.utils.prompt_loader._global_loader
        try:
            src.utils.prompt_loader._global_loader = PromptLoader(prompts_dir=temp_prompts_dir)
            
            rendered = load_and_render_prompt(
                category="transcription",
                prompt_name="basic_transcription",
                language="日本語",
                custom_instructions="これはテスト用のカスタム指示です。"
            )
            
            assert "**言語**: 日本語" in rendered
            assert "オーバーライド指示事項" in rendered
            assert "これはテスト用のカスタム指示です。" in rendered
        finally:
            # 元のローダーに戻す
            src.utils.prompt_loader._global_loader = original_loader
    
    def test_get_available_prompts(self, temp_prompts_dir):
        """利用可能なプロンプトの一覧を取得できることを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        available_prompts = loader.get_available_prompts()
        
        assert "transcription" in available_prompts
        assert "quality_check" in available_prompts
        assert "minutes_generation" in available_prompts
        
        assert "basic_transcription" in available_prompts["transcription"]
        assert "legacy_transcription" in available_prompts["transcription"]
        assert "basic_check" in available_prompts["quality_check"]
        assert "lecture_notes" in available_prompts["minutes_generation"]
    
    def test_cache_mechanism(self, temp_prompts_dir):
        """キャッシュ機能が正しく動作することを確認"""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)
        
        # 初回読み込み
        template1 = loader.load_prompt("transcription", "basic_transcription")
        
        # override_prompts.mdファイルを変更
        override_path = temp_prompts_dir / "override_prompts.md"
        with open(override_path, "a", encoding="utf-8") as f:
            f.write("\n# この変更はキャッシュがクリアされるまで反映されません")
        
        # キャッシュから読み込まれるため変更は反映されない
        template2 = loader.load_prompt("transcription", "basic_transcription")
        assert template1 is template2
        
        # キャッシュをクリア
        loader.clear_cache()
        
        # 再度読み込み（ファイルから読み込まれる）
        template3 = loader.load_prompt("transcription", "basic_transcription")
        assert template1 is not template3


if __name__ == "__main__":
    # 手動テスト用
    import sys
    import tempfile
    
    # 一時ディレクトリにテスト用ファイルを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        test = TestConsolidatedPromptLoader()
        test._create_base_prompts_file(Path(temp_dir))
        test._create_school_prompts_file(Path(temp_dir))
        test._create_override_prompts_file(Path(temp_dir))
        
        legacy_dir = Path(temp_dir) / "transcription"
        legacy_dir.mkdir(exist_ok=True)
        test._create_legacy_prompt_file(legacy_dir)
        
        # PromptLoaderを初期化
        loader = PromptLoader(prompts_dir=temp_dir)
        
        # 各プロンプトを読み込んで表示
        print("\n=== base_prompts.md から読み込み ===")
        template = loader.load_prompt("quality_check", "basic_check")
        print(f"Name: {template.name}")
        print(f"Overview: {template.overview[:50]}...")
        print(f"Parameters: {list(template.parameters.keys())}")
        print(f"Content: {template.content[:50]}...")
        
        print("\n=== school_prompts.md から読み込み ===")
        template = loader.load_prompt("minutes_generation", "lecture_notes")
        print(f"Name: {template.name}")
        print(f"Overview: {template.overview[:50]}...")
        print(f"Parameters: {list(template.parameters.keys())}")
        print(f"Content: {template.content[:50]}...")
        
        print("\n=== override_prompts.md から読み込み（オーバーライド機能） ===")
        template = loader.load_prompt("transcription", "basic_transcription")
        print(f"Name: {template.name}")
        print(f"Overview: {template.overview[:50]}...")
        print(f"Parameters: {list(template.parameters.keys())}")
        print(f"Content: {template.content[:50]}...")
        
        print("\n=== 従来の個別ファイルから読み込み ===")
        template = loader.load_prompt("transcription", "legacy_transcription")
        print(f"Name: {template.name}")
        print(f"Overview: {template.overview[:50]}...")
        print(f"Parameters: {list(template.parameters.keys())}")
        print(f"Content: {template.content[:50]}...")
        
        print("\n=== 利用可能なプロンプト一覧 ===")
        available_prompts = loader.get_available_prompts()
        for category, prompts in available_prompts.items():
            print(f"{category}: {prompts}")