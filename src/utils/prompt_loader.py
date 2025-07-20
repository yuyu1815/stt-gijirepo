"""
プロンプト読み込みユーティリティ

Markdownファイルからプロンプトを読み込み、パラメータを置換して利用するための機能を提供します。
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """プロンプトテンプレートを表すデータクラス"""
    name: str
    overview: str
    parameters: Dict[str, str]
    content: str
    examples: Optional[str] = None
    notes: Optional[str] = None


class PromptLoader:
    """プロンプト読み込みクラス"""
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        プロンプトローダーを初期化
        
        Args:
            prompts_dir: プロンプト定義ディレクトリのパス
        """
        if prompts_dir is None:
            # デフォルトのプロンプトディレクトリを設定
            current_dir = Path(__file__).parent
            self.prompts_dir = current_dir.parent / "prompts" / "definitions"
        else:
            self.prompts_dir = Path(prompts_dir)
        
        self._cache: Dict[str, PromptTemplate] = {}
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")
    
    def load_prompt(self, category: str, prompt_name: str) -> PromptTemplate:
        """
        指定されたカテゴリとプロンプト名からプロンプトを読み込む
        
        Args:
            category: プロンプトカテゴリ（例: "transcription", "minutes_generation"）
            prompt_name: プロンプト名（例: "basic_transcription", "detailed_minutes"）
            
        Returns:
            PromptTemplate: 読み込まれたプロンプトテンプレート
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトファイルの形式が不正な場合
        """
        cache_key = f"{category}/{prompt_name}"
        
        # キャッシュから取得を試行
        if cache_key in self._cache:
            logger.debug(f"Loading prompt from cache: {cache_key}")
            return self._cache[cache_key]
        
        # ファイルパスを構築
        file_path = self.prompts_dir / category / f"{prompt_name}.md"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        logger.info(f"Loading prompt from file: {file_path}")
        
        # Markdownファイルを読み込み
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # プロンプトテンプレートを解析
        template = self._parse_markdown(content, prompt_name)
        
        # キャッシュに保存
        self._cache[cache_key] = template
        
        return template
    
    def _parse_markdown(self, content: str, prompt_name: str) -> PromptTemplate:
        """
        Markdownコンテンツを解析してPromptTemplateを作成
        
        Args:
            content: Markdownファイルの内容
            prompt_name: プロンプト名
            
        Returns:
            PromptTemplate: 解析されたプロンプトテンプレート
        """
        lines = content.split('\n')
        
        # セクションを解析
        sections = self._extract_sections(lines)
        
        # 必須セクションの確認
        if '概要' not in sections:
            raise ValueError(f"Missing required section '概要' in prompt: {prompt_name}")
        if 'プロンプト本文' not in sections:
            raise ValueError(f"Missing required section 'プロンプト本文' in prompt: {prompt_name}")
        
        # パラメータを解析
        parameters = {}
        if 'パラメータ' in sections:
            parameters = self._parse_parameters(sections['パラメータ'])
        
        # プロンプトテンプレートを作成
        template = PromptTemplate(
            name=prompt_name,
            overview=sections['概要'].strip(),
            parameters=parameters,
            content=sections['プロンプト本文'].strip(),
            examples=sections.get('使用例', '').strip() if sections.get('使用例') else None,
            notes=sections.get('注意事項', '').strip() if sections.get('注意事項') else None
        )
        
        return template
    
    def _extract_sections(self, lines: List[str]) -> Dict[str, str]:
        """
        Markdownの行からセクションを抽出
        
        Args:
            lines: Markdownファイルの行リスト
            
        Returns:
            Dict[str, str]: セクション名をキーとした内容の辞書
        """
        sections = {}
        current_section = None
        current_content = []
        
        for line in lines:
            # セクションヘッダーを検出（## で始まる行）
            if line.startswith('## '):
                # 前のセクションを保存
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                
                # 新しいセクションを開始
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # 最後のセクションを保存
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _parse_parameters(self, param_section: str) -> Dict[str, str]:
        """
        パラメータセクションを解析
        
        Args:
            param_section: パラメータセクションの内容
            
        Returns:
            Dict[str, str]: パラメータ名をキーとした説明の辞書
        """
        parameters = {}
        lines = param_section.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('- `{') and '}`:' in line:
                # パラメータ行を解析: - `{param_name}`: 説明
                match = re.match(r'- `\{([^}]+)\}`: (.+)', line)
                if match:
                    param_name = match.group(1)
                    description = match.group(2)
                    parameters[param_name] = description
        
        return parameters
    
    def render_prompt(self, template: PromptTemplate, **kwargs) -> str:
        """
        プロンプトテンプレートにパラメータを適用してレンダリング
        
        Args:
            template: プロンプトテンプレート
            **kwargs: テンプレートに適用するパラメータ
            
        Returns:
            str: レンダリングされたプロンプト
        """
        content = template.content
        
        # パラメータを置換
        for param_name, value in kwargs.items():
            placeholder = f"{{{param_name}}}"
            if value is not None:
                content = content.replace(placeholder, str(value))
            else:
                # None の場合は空文字で置換
                content = content.replace(placeholder, "")
        
        # 未置換のパラメータをチェック
        remaining_params = re.findall(r'\{([^}]+)\}', content)
        if remaining_params:
            logger.warning(f"Unresolved parameters in prompt: {remaining_params}")
        
        return content
    
    def get_available_prompts(self) -> Dict[str, List[str]]:
        """
        利用可能なプロンプトの一覧を取得
        
        Returns:
            Dict[str, List[str]]: カテゴリをキーとしたプロンプト名のリスト
        """
        available_prompts = {}
        
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return available_prompts
        
        # カテゴリディレクトリを走査
        for category_dir in self.prompts_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                category_name = category_dir.name
                prompts = []
                
                # プロンプトファイルを走査
                for prompt_file in category_dir.rglob('*.md'):
                    if prompt_file.name != 'README.md':
                        # サブディレクトリがある場合はパスを含める
                        relative_path = prompt_file.relative_to(category_dir)
                        prompt_name = str(relative_path.with_suffix(''))
                        prompts.append(prompt_name)
                
                if prompts:
                    available_prompts[category_name] = sorted(prompts)
        
        return available_prompts
    
    def clear_cache(self):
        """プロンプトキャッシュをクリア"""
        self._cache.clear()
        logger.info("Prompt cache cleared")


# 便利な関数
def load_and_render_prompt(category: str, prompt_name: str, **kwargs) -> str:
    """
    プロンプトを読み込んでレンダリングする便利関数
    
    Args:
        category: プロンプトカテゴリ
        prompt_name: プロンプト名
        **kwargs: テンプレートパラメータ
        
    Returns:
        str: レンダリングされたプロンプト
    """
    loader = PromptLoader()
    template = loader.load_prompt(category, prompt_name)
    return loader.render_prompt(template, **kwargs)


# グローバルインスタンス（シングルトンパターン）
_global_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """
    グローバルプロンプトローダーインスタンスを取得
    
    Returns:
        PromptLoader: プロンプトローダーインスタンス
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = PromptLoader()
    return _global_loader