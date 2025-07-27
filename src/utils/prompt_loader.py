"""
プロンプト読み込みユーティリティ

Markdownファイルからプロンプトを読み込み、パラメータを置換して利用するための機能を提供します。
新しいバージョンでは、個別のMarkdownファイルだけでなく、統合されたプロンプト定義ファイルからも
プロンプトを読み込むことができます。
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
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


def _parse_parameters(param_section: str) -> Dict[str, str]:
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


def _extract_sections(lines: List[str]) -> Dict[str, str]:
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


def _parse_markdown(content: str, prompt_name: str) -> PromptTemplate:
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
    sections = _extract_sections(lines)

    # 必須セクションの確認
    if '概要' not in sections:
        raise ValueError(f"Missing required section '概要' in prompt: {prompt_name}")
    if 'プロンプト本文' not in sections:
        raise ValueError(f"Missing required section 'プロンプト本文' in prompt: {prompt_name}")

    # パラメータを解析
    parameters = {}
    if 'パラメータ' in sections:
        parameters = _parse_parameters(sections['パラメータ'])

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


class PromptLoader:
    """プロンプト読み込みクラス"""
    
    # 統合プロンプトファイル名
    CONSOLIDATED_FILES = [
        "base_prompts_en.md",
        "base_prompts_ja.md",
        "meeting_prompts_ja.md",
        "school_prompts_ja.md",
        "override_prompts.md"
    ]
    
    # 言語ごとのベースプロンプトファイル
    BASE_PROMPT_FILES = {
        "en": "base_prompts_en.md",
        "ja": "base_prompts_ja.md"
    }
    
    # プロンプトタイプごとのファイル（デフォルト値）
    DEFAULT_PROMPT_TYPE_FILES = {
        "meeting": "meeting_prompts_ja.md",
        "school": "school_prompts_ja.md"
    }
    
    # ユーザーフレンドリーな名前から内部IDへのマッピング（デフォルト値）
    DEFAULT_PROMPT_TYPE_MAPPING = {
        "会議": "meeting",
        "授業": "school"
    }
    
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
        self._prompt_map: Dict[str, str] = {}  # キー: "category/prompt_name", 値: ファイルパス
        self._initialized = False
        
        # プロンプトタイプの設定を読み込む
        self.PROMPT_TYPE_FILES = self.DEFAULT_PROMPT_TYPE_FILES.copy()
        self.PROMPT_TYPE_MAPPING = self.DEFAULT_PROMPT_TYPE_MAPPING.copy()
        self._load_prompt_type_config()
        
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")
        
    def _load_prompt_type_config(self):
        """
        settings.jsonからプロンプトタイプの設定を読み込む
        
        設定ファイルに以下のような形式でプロンプトタイプの設定がある場合、
        それを読み込んでPROMPT_TYPE_FILESとPROMPT_TYPE_MAPPINGを更新する
        
        例:
        {
          "prompt_types": {
            "会議": {
              "file": "meeting_prompts_ja.md",
              "internal_id": "meeting"
            },
            "授業": {
              "file": "school_prompts_ja.md",
              "internal_id": "school"
            }
          }
        }
        """
        import json
        from pathlib import Path
        
        settings_file = Path("settings.json")
        if not settings_file.exists():
            logger.debug("settings.jsonが見つからないため、デフォルトのプロンプトタイプ設定を使用します")
            return
            
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
            # prompt_types設定があれば読み込む
            if "prompt_types" in settings:
                prompt_types = settings["prompt_types"]
                
                # 各プロンプトタイプの設定を処理
                for user_name, config in prompt_types.items():
                    # _commentキーはスキップ
                    if user_name == "_comment":
                        continue
                        
                    # 必要な情報が揃っているか確認
                    if "file" in config and "internal_id" in config:
                        file_name = config["file"]
                        internal_id = config["internal_id"]
                        
                        # マッピングを更新
                        self.PROMPT_TYPE_MAPPING[user_name] = internal_id
                        self.PROMPT_TYPE_FILES[internal_id] = file_name
                        
                        logger.debug(f"プロンプトタイプ設定を読み込みました: {user_name} -> {internal_id} -> {file_name}")
                    else:
                        logger.warning(f"プロンプトタイプ設定が不完全です: {user_name}")
                
                logger.info(f"settings.jsonから{len(prompt_types) - (1 if '_comment' in prompt_types else 0)}個のプロンプトタイプ設定を読み込みました")
            else:
                logger.debug("settings.jsonにprompt_types設定がないため、デフォルトのプロンプトタイプ設定を使用します")
                
        except Exception as e:
            logger.warning(f"プロンプトタイプ設定の読み込みに失敗しました: {e}")
            logger.debug("デフォルトのプロンプトタイプ設定を使用します")
    
    def _initialize_prompt_map(self):
        """統合プロンプトファイルからプロンプトマップを初期化"""
        if self._initialized:
            return
        
        # 統合プロンプトファイルを処理
        for filename in self.CONSOLIDATED_FILES:
            file_path = self.prompts_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # XMLタグからプロンプトを抽出
                    prompts = self._extract_prompts_from_consolidated(content, file_path)
                    for tag, prompt_content in prompts:
                        # タグから category と prompt_name を抽出
                        parts = tag.split('_', 1)
                        if len(parts) == 2:
                            category, prompt_name = parts
                            
                            
                            cache_key = f"{category}/{prompt_name}"
                            
                            # override_prompts.md のプロンプトは常に優先
                            if filename == "override_prompts.md" or cache_key not in self._prompt_map:
                                self._prompt_map[cache_key] = file_path
                                logger.debug(f"Added prompt '{cache_key}' from {file_path}")
                except Exception as e:
                    logger.error(f"Error processing consolidated file {file_path}: {e}")
                    # スタックトレースを出力
                    import traceback
                    logger.error(traceback.format_exc())
        
        # 従来の個別ファイルも処理（後方互換性のため）
        for category_dir in self.prompts_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                category_name = category_dir.name
                for prompt_file in category_dir.rglob('*.md'):
                    if prompt_file.name != 'README.md':
                        relative_path = prompt_file.relative_to(category_dir)
                        prompt_name = str(relative_path.with_suffix(''))
                        cache_key = f"{category_name}/{prompt_name}"
                        
                        # 統合ファイルで定義されていない場合のみ追加
                        if cache_key not in self._prompt_map:
                            self._prompt_map[cache_key] = prompt_file
                            logger.debug(f"Added legacy prompt '{cache_key}' from {prompt_file}")
        
        self._initialized = True
        logger.debug(f"Prompt map initialized with {len(self._prompt_map)} prompts: {list(self._prompt_map.keys())}")
    
    def _extract_prompts_from_consolidated(self, content: str, file_path: Path) -> List[Tuple[str, str]]:
        """
        統合プロンプトファイルからXMLタグで囲まれたプロンプトを抽出
        
        Args:
            content: ファイルの内容
            file_path: ファイルパス（ログ用）
            
        Returns:
            List[Tuple[str, str]]: (タグ名, プロンプト内容) のリスト
        """
        prompts = []
        # XMLタグを検出するための正規表現
        # 注意: 複数行にまたがるマッチングのためにre.DOTALLフラグを使用
        pattern = r'<([a-zA-Z0-9_]+)>(.*?)</\1>'
        
        # re.DOTALL フラグで複数行にまたがるマッチングを有効化
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            tag = match.group(1)
            prompt_content = match.group(2).strip()
            prompts.append((tag, prompt_content))
            logger.debug(f"Extracted prompt with tag '{tag}' from {file_path}")
        
        return prompts
    
    def load_prompt_with_language(self, category: str, prompt_name: str, language: str = "ja", prompt_type: Optional[str] = None) -> PromptTemplate:
        """
        言語とプロンプトタイプを指定してプロンプトを読み込む
        
        Args:
            category: プロンプトカテゴリ（例: "transcription", "minutes_generation"）
            prompt_name: プロンプト名（例: "basic_transcription", "detailed_minutes"）
            language: 言語コード（例: "ja", "en"）
            prompt_type: プロンプトタイプ（例: "meeting", "school"）またはユーザーフレンドリーな名前（例: "会議", "授業"）
            
        Returns:
            PromptTemplate: 読み込まれたプロンプトテンプレート
            
        Raises:
            FileNotFoundError: プロンプトが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        # プロンプトマップを初期化
        if not self._initialized:
            logger.debug("Initializing prompt map")
            self._initialize_prompt_map()
        
        # タグを構築
        tag = f"{category}_{prompt_name}"
        logger.debug(f"Looking for prompt tag: {tag}")
        
        # 言語に基づいてベースプロンプトファイルを選択
        base_file = self.BASE_PROMPT_FILES.get(language, self.BASE_PROMPT_FILES["ja"])
        base_file_path = self.prompts_dir / base_file
        
        # プロンプトタイプが指定されている場合、そのファイルも選択
        type_file_path = None
        internal_prompt_type = None
        
        if prompt_type:
            # ユーザーフレンドリーな名前から内部IDへのマッピングを試みる
            if prompt_type in self.PROMPT_TYPE_MAPPING:
                internal_prompt_type = self.PROMPT_TYPE_MAPPING[prompt_type]
                logger.debug(f"Mapped prompt type '{prompt_type}' to internal ID '{internal_prompt_type}'")
            else:
                # マッピングがない場合は直接内部IDとして使用
                internal_prompt_type = prompt_type
                
            # 内部IDに対応するファイルを取得
            if internal_prompt_type in self.PROMPT_TYPE_FILES:
                type_file = self.PROMPT_TYPE_FILES[internal_prompt_type]
                type_file_path = self.prompts_dir / type_file
                logger.debug(f"Using prompt type file: {type_file}")
            else:
                logger.warning(f"Prompt type '{internal_prompt_type}' not found in PROMPT_TYPE_FILES")
        
        # ベースプロンプトを読み込む
        base_content = None
        if base_file_path.exists():
            try:
                with open(base_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                pattern = re.compile(f'<{tag}>(.*?)</{tag}>', re.DOTALL)
                match = pattern.search(file_content)
                
                if match:
                    base_content = match.group(1).strip()
                    logger.debug(f"Found base prompt for tag '{tag}' in {base_file_path}")
            except Exception as e:
                logger.error(f"Error reading base prompt file {base_file_path}: {e}")
        
        # プロンプトタイプが指定されていて、そのファイルが存在する場合、オーバーライドを試みる
        override_content = None
        if type_file_path and type_file_path.exists():
            try:
                with open(type_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                pattern = re.compile(f'<{tag}>(.*?)</{tag}>', re.DOTALL)
                match = pattern.search(file_content)
                
                if match:
                    override_content = match.group(1).strip()
                    logger.debug(f"Found override prompt for tag '{tag}' in {type_file_path}")
            except Exception as e:
                logger.error(f"Error reading override prompt file {type_file_path}: {e}")
        
        # ベースプロンプトが見つからない場合はエラー
        if base_content is None and override_content is None:
            error_msg = f"Prompt not found for tag '{tag}' in language '{language}'"
            if prompt_type:
                error_msg += f" and prompt type '{prompt_type}'"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # オーバーライドが見つかった場合はそれを使用、そうでなければベースプロンプトを使用
        content = override_content if override_content is not None else base_content
        
        # プロンプトテンプレートを解析
        logger.debug(f"Parsing markdown content for {prompt_name}")
        template = _parse_markdown(content, prompt_name)
        
        # キャッシュに保存
        cache_key = f"{category}/{prompt_name}/{language}/{prompt_type or 'none'}"
        self._cache[cache_key] = template
        
        return template
    
    def load_prompt(self, category: str, prompt_name: str) -> PromptTemplate:
        """
        指定されたカテゴリとプロンプト名からプロンプトを読み込む
        
        Args:
            category: プロンプトカテゴリ（例: "transcription", "minutes_generation"）
            prompt_name: プロンプト名（例: "basic_transcription", "detailed_minutes"）
            
        Returns:
            PromptTemplate: 読み込まれたプロンプトテンプレート
            
        Raises:
            FileNotFoundError: プロンプトが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        cache_key = f"{category}/{prompt_name}"
        logger.debug(f"Attempting to load prompt: {cache_key}")
        
        # キャッシュから取得を試行
        if cache_key in self._cache:
            logger.debug(f"Loading prompt from cache: {cache_key}")
            return self._cache[cache_key]
        
        # プロンプトマップを初期化
        if not self._initialized:
            logger.debug("Initializing prompt map")
            self._initialize_prompt_map()
        
        # プロンプトマップからファイルパスを取得
        if cache_key not in self._prompt_map:
            logger.debug(f"Prompt not found in map, checking legacy path: {cache_key}")
            # 従来の方法でファイルパスを構築（後方互換性のため）
            legacy_file_path = self.prompts_dir / category / f"{prompt_name}.md"
            if legacy_file_path.exists():
                logger.debug(f"Found legacy file: {legacy_file_path}")
                self._prompt_map[cache_key] = legacy_file_path
            else:
                # 統合ファイルを直接チェック
                for filename in self.CONSOLIDATED_FILES:
                    file_path = self.prompts_dir / filename
                    if file_path.exists():
                        logger.debug(f"Checking consolidated file: {file_path}")
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            
                            tag = f"{category}_{prompt_name}"
                            if f"<{tag}>" in file_content and f"</{tag}>" in file_content:
                                logger.debug(f"Found prompt tag '{tag}' in {file_path}")
                                self._prompt_map[cache_key] = file_path
                                break
                        except Exception as e:
                            logger.error(f"Error checking consolidated file {file_path}: {e}")
                
                if cache_key not in self._prompt_map:
                    logger.error(f"Prompt not found: {cache_key}")
                    logger.error(f"Available prompts: {list(self._prompt_map.keys())}")
                    raise FileNotFoundError(f"Prompt not found: {cache_key}")
        
        file_path = self._prompt_map[cache_key]
        logger.info(f"Loading prompt '{cache_key}' from {file_path}")
        
        # ファイルを読み込み
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # 統合ファイルの場合はタグからプロンプトを抽出
        if file_path.name in self.CONSOLIDATED_FILES:
            tag = f"{category}_{prompt_name}"
            logger.debug(f"Extracting prompt with tag '{tag}' from {file_path}")
            pattern = re.compile(f'<{tag}>(.*?)</{tag}>', re.DOTALL)
            match = pattern.search(file_content)
            
            if match:
                content = match.group(1).strip()
                logger.debug(f"Extracted prompt content (first 50 chars): {content[:50]}...")
            else:
                logger.error(f"Prompt tag '{tag}' not found in {file_path}")
                # ファイル内のすべてのタグを表示
                all_tags = re.findall(r'<([a-zA-Z0-9_]+)>', file_content)
                logger.error(f"Available tags in {file_path}: {all_tags}")
                raise ValueError(f"Prompt tag '{tag}' not found in {file_path}")
        else:
            # 個別ファイルの場合はファイル全体を使用
            logger.debug(f"Using entire file content for {file_path}")
            content = file_content
        
        # プロンプトテンプレートを解析
        logger.debug(f"Parsing markdown content for {prompt_name}")
        template = _parse_markdown(content, prompt_name)
        
        # キャッシュに保存
        self._cache[cache_key] = template
        
        return template

    @staticmethod
    def render_prompt(template: PromptTemplate, **kwargs) -> str:
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
        
        # プロンプトマップを初期化
        if not self._initialized:
            self._initialize_prompt_map()
        
        # プロンプトマップからカテゴリごとにプロンプトを整理
        for cache_key in self._prompt_map:
            parts = cache_key.split('/')
            if len(parts) == 2:
                category, prompt_name = parts
                if category not in available_prompts:
                    available_prompts[category] = []
                available_prompts[category].append(prompt_name)
        
        # 各カテゴリのプロンプトリストをソート
        for category in available_prompts:
            available_prompts[category] = sorted(available_prompts[category])
        
        # 従来の方法でも検索（後方互換性のため）
        for category_dir in self.prompts_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                category_name = category_dir.name
                if category_name not in available_prompts:
                    available_prompts[category_name] = []
                
                # プロンプトファイルを走査
                for prompt_file in category_dir.rglob('*.md'):
                    if prompt_file.name != 'README.md':
                        # サブディレクトリがある場合はパスを含める
                        relative_path = prompt_file.relative_to(category_dir)
                        prompt_name = str(relative_path.with_suffix(''))
                        if prompt_name not in available_prompts[category_name]:
                            available_prompts[category_name].append(prompt_name)
                
                # 空のカテゴリは削除
                if not available_prompts[category_name]:
                    del available_prompts[category_name]
                else:
                    available_prompts[category_name] = sorted(available_prompts[category_name])
        
        return available_prompts
    
    def clear_cache(self):
        """プロンプトキャッシュとプロンプトマップをクリア"""
        self._cache.clear()
        self._prompt_map.clear()
        self._initialized = False
        logger.info("Prompt cache and map cleared")


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
    loader = get_prompt_loader()  # グローバルローダーを使用
    template = loader.load_prompt(category, prompt_name)
    return loader.render_prompt(template, **kwargs)


def load_and_render_prompt_with_language(category: str, prompt_name: str, language: str = "ja", prompt_type: Optional[str] = None, **kwargs) -> str:
    """
    言語とプロンプトタイプを指定してプロンプトを読み込んでレンダリングする便利関数
    
    Args:
        category: プロンプトカテゴリ
        prompt_name: プロンプト名
        language: 言語コード（例: "ja", "en"）
        prompt_type: プロンプトタイプ（例: "meeting", "school"）
        **kwargs: テンプレートパラメータ
        
    Returns:
        str: レンダリングされたプロンプト
    """
    loader = get_prompt_loader()  # グローバルローダーを使用
    template = loader.load_prompt_with_language(category, prompt_name, language, prompt_type)
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