#!/usr/bin/env python
"""
音声文字起こし・議事録自動生成ツール

このスクリプトは、アプリケーションのエントリーポイントです。
"""
import sys
from src.application.cli import main

if __name__ == "__main__":
    sys.exit(main())