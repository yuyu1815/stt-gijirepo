#!/usr/bin/env python
"""
Script to check if all prompts can be loaded correctly.
"""

import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.prompt_loader import get_prompt_loader
from src.utils.logging_config import get_logger
from src.utils.retry_utils import method_error_handler
from src.utils.error_handling import STTError

logger = get_logger(__name__)

@method_error_handler(STTError, "プロンプトチェックに失敗")
def check_prompt(loader, category, prompt_name):
    """
    Check a single prompt.
    
    Args:
        loader: The prompt loader
        category: The prompt category
        prompt_name: The prompt name
        
    Returns:
        dict: The result of the check
    """
    try:
        prompt = loader.load_prompt(category, prompt_name)
        logger.info(f"✓ Successfully loaded prompt: {category}/{prompt_name}")
        return {
            "success": True,
            "category": category,
            "prompt_name": prompt_name
        }
    except Exception as e:
        error_message = f"✗ Failed to load prompt: {category}/{prompt_name} - {str(e)}"
        logger.error(error_message)
        return {
            "success": False,
            "category": category,
            "prompt_name": prompt_name,
            "error": str(e)
        }

def check_all_prompts():
    """
    Check if all prompts can be loaded correctly.
    
    Returns:
        tuple: (success_count, error_count, error_details)
    """
    loader = get_prompt_loader()
    available_prompts = loader.get_available_prompts()
    
    logger.info(f"Found {sum(len(prompts) for prompts in available_prompts.values())} prompts in {len(available_prompts)} categories")
    
    results = []
    
    # Check each prompt
    for category, prompts in available_prompts.items():
        logger.info(f"Checking category: {category} ({len(prompts)} prompts)")
        
        for prompt_name in prompts:
            result = check_prompt(loader, category, prompt_name)
            results.append(result)
    
    # Analyze results
    success_count = sum(1 for r in results if r["success"])
    error_count = len(results) - success_count
    error_details = [r for r in results if not r["success"]]
    
    return success_count, error_count, error_details

def generate_report(success_count, error_count, error_details):
    """
    Generate a report of the prompt check results.
    
    Args:
        success_count: Number of successfully loaded prompts
        error_count: Number of prompts that failed to load
        error_details: Details of the errors
        
    Returns:
        str: The report as a string
    """
    total = success_count + error_count
    success_rate = (success_count / total) * 100 if total > 0 else 0
    
    report = [
        "# プロンプト読み込みチェックレポート",
        "",
        f"実行日時: {Path(__file__).stat().st_mtime}",
        "",
        "## 概要",
        f"- 総プロンプト数: {total}",
        f"- 成功: {success_count} ({success_rate:.1f}%)",
        f"- 失敗: {error_count} ({100 - success_rate:.1f}%)",
        ""
    ]
    
    if error_count > 0:
        report.append("## エラー詳細")
        report.append("")
        
        for i, error in enumerate(error_details, 1):
            report.append(f"### {i}. {error['category']}/{error['prompt_name']}")
            report.append(f"エラー: {error['error']}")
            report.append("")
    
    report.append("## 推奨事項")
    report.append("")
    
    if error_count > 0:
        report.append("以下の問題を修正してください:")
        report.append("")
        report.append("1. 必須セクションが欠けているプロンプトファイルを修正")
        report.append("   - すべてのプロンプトファイルには `## 概要` と `## プロンプト本文` セクションが必要です")
        report.append("2. プロンプトファイルの形式を統一")
        report.append("   - 標準的なセクション構造: 概要、パラメータ（必要な場合）、プロンプト本文、使用例（オプション）、注意事項（オプション）")
        report.append("")
    else:
        report.append("すべてのプロンプトが正常に読み込まれました。特に問題はありません。")
        report.append("")
    
    return "\n".join(report)

@method_error_handler(STTError, "プロンプトチェックメイン関数に失敗")
def main():
    """Main function."""
    logger.info("Starting prompt check")
    
    success_count, error_count, error_details = check_all_prompts()
    
    report = generate_report(success_count, error_count, error_details)
    
    # Print the report to stdout
    print(report)
    
    # Save the report to a file
    report_path = Path(__file__).parent.parent.parent / "prompt_check_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"Report saved to {report_path}")
    
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())