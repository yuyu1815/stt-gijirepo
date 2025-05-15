import time
import requests
import json
import os
import math
import re
from pydub import AudioSegment
from google import genai
import argparse
import cv2
import numpy as np
import pprint
from notion_uploader import NotionUploader
from datetime import datetime
import concurrent.futures
from class_info_utils import get_class_info
from lang_utils import get_string

def load_prompt(prompt_file):
    """プロンプトファイルを読み込む関数

    Args:
        prompt_file (str): プロンプトファイルのパス

    Returns:
        str: プロンプトの内容
    """
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 「グレイヴ・アクセント*3」という記述を実際のバッククォート（```）に置き換える
            content = content.replace("グレイヴ・アクセント*3", "```")
            return content
    except Exception as e:
        print(f"プロンプトファイルの読み込みに失敗しました: {e}")
        return None

def is_video_dark(file_path, darkness_threshold=10):
    """動画が真っ暗かどうかを判定する関数
    4箇所のフレームをチェックして真っ暗かどうかを判定します"""
    try:
        # 動画ファイルを開く
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            print(f"エラー: 動画ファイル '{file_path}' を開けませんでした。")
            return False

        # 動画の総フレーム数を取得
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            print(f"エラー: 動画ファイル '{file_path}' のフレーム数が取得できませんでした。")
            return False

        # 4箇所のフレーム位置を計算（10%, 30%, 70%, 90%の位置）
        check_positions = [
            int(total_frames * 0.1),
            int(total_frames * 0.3),
            int(total_frames * 0.7),
            int(total_frames * 0.9)
        ]

        # 暗いフレームのカウント
        dark_frames = 0
        frames_checked = 0

        for position in check_positions:
            # 指定フレームに移動
            cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ret, frame = cap.read()

            if not ret:
                continue

            frames_checked += 1

            # フレームの平均輝度を計算
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray)

            # 輝度が閾値以下なら暗いフレームとしてカウント
            if avg_brightness < darkness_threshold:
                dark_frames += 1

        cap.release()

        # 実際にチェックしたフレーム数が0の場合はエラー
        if frames_checked == 0:
            print(f"エラー: 動画ファイル '{file_path}' のフレームが読み込めませんでした。")
            return False

        # 暗いフレームの割合が90%以上なら真っ暗と判定
        dark_ratio = dark_frames / frames_checked
        print(f"暗いフレームの割合: {dark_ratio:.2f} ({dark_frames}/{frames_checked})")

        return dark_ratio >= 0.9

    except Exception as e:
        print(f"動画の明るさ判定中にエラーが発生しました: {str(e)}")
        return False

def convert_video_to_aac(video_path):
    """動画からAACオーディオを抽出する関数"""
    try:
        # プロジェクト内に一時ファイル用のフォルダを作成
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_aac")
        os.makedirs(temp_dir, exist_ok=True)

        # 出力ファイル名を生成
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(temp_dir, f"{base_name}.aac")

        # 動画からオーディオを抽出
        audio = AudioSegment.from_file(video_path)
        audio.export(output_path, format="adts")  # AACはadtsフォーマットで出力

        print(f"動画からAACオーディオを抽出しました: {output_path}")
        return output_path
    except Exception as e:
        print(f"動画からオーディオ抽出中にエラーが発生しました: {str(e)}")
        return None

def get_audio_duration(file_path):
    """音声ファイルの長さ（秒）を取得する関数"""
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000  # ミリ秒から秒へ変換

def split_audio(file_path, chunk_duration, start_file_index=0, start_time_seconds=0):
    """指定した長さで音声ファイルを分割する関数

    Args:
        file_path: 音声ファイルのパス
        chunk_duration: 各チャンクの長さ（秒）
        start_file_index: 開始するファイル番号（0始まり）
        start_time_seconds: 開始する時間（秒）
    """
    audio = AudioSegment.from_file(file_path)
    total_duration = len(audio) / 1000  # ミリ秒から秒へ変換

    # 開始時間を適用（ミリ秒に変換）
    start_time_ms = start_time_seconds * 1000

    # 開始時間が音声の長さを超えている場合は調整
    if start_time_ms >= len(audio):
        print(f"警告: 指定された開始時間 {start_time_seconds}秒 が音声の長さ {total_duration}秒 を超えています。開始時間を0秒に設定します。")
        start_time_ms = 0
        start_time_seconds = 0

    chunks = []
    # 開始ファイル番号から処理を開始
    for i in range(start_file_index, math.ceil((total_duration - start_time_seconds) / chunk_duration) + start_file_index):
        # 最初のチャンクは指定された開始時間から始める
        if i == start_file_index:
            start_ms = start_time_ms
        else:
            # 2つ目以降のチャンクは通常通り計算
            start_ms = start_time_ms + (i - start_file_index) * chunk_duration * 1000

        end_ms = min(start_ms + chunk_duration * 1000, len(audio))

        # 開始時間と終了時間が同じ場合はスキップ
        if start_ms >= end_ms:
            continue

        chunk = audio[start_ms:end_ms]

        # プロジェクト内に一時ファイル用のフォルダを作成
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)

        # チャンク用の一時ファイルを作成（プロジェクトディレクトリ内）
        temp_filename = f"chunk_{i}_{int(start_ms / 1000)}_{int(end_ms / 1000)}.aac"
        chunk_path = os.path.join(temp_dir, temp_filename)
        chunk.export(chunk_path, format="adts")
        # 実際の開始時間と終了時間をタプルとして保存
        actual_start_time = start_ms / 1000  # 秒に変換
        actual_end_time = end_ms / 1000  # 秒に変換
        chunks.append((chunk_path, actual_start_time, actual_end_time))

    return chunks

def generate_content_with_retry(client, model_name, contents, max_retries=5):
    """
    Gemini APIのgenerate_contentを実行し、応答が"1. None"の場合は再試行する関数

    Args:
        client: Gemini APIクライアント
        model_name: 使用するモデル名
        contents: 生成コンテンツのリクエスト内容
        max_retries: 最大再試行回数（デフォルト: 5）

    Returns:
        生成されたコンテンツのレスポンス。エラーの場合はNone
    """
    retries = 0
    while retries < max_retries:
        try:
            response = client.models.generate_content(
                model=model_name, contents=contents
            )

            # "1. None"の応答をチェック
            if response.text is None:
                print(f"Geminiからの応答がNoneでした。再試行します（{retries+1}/{max_retries}）")
                retries += 1
                time.sleep(30)  # 30秒待機してから再試行
                continue
            elif response.text.strip() == "1. None":
                print(f"Geminiからの応答が「1. None」でした。再試行します（{retries+1}/{max_retries}）")
                retries += 1
                time.sleep(30)  # 30秒待機してから再試行
                continue

            return response
        except Exception as e:
            print(f"Gemini APIリクエスト中にエラーが発生しました: {e}")
            retries += 1
            if retries < max_retries:
                print(f"再試行します（{retries}/{max_retries}）")
                time.sleep(30)  # 30秒待機してから再試行
            else:
                print(f"最大再試行回数（{max_retries}）に達しました。")
                return None

    return None

def transcribe_audio_with_gemini(file_path: str) -> dict | None:
    """
    Gemini APIを使用して音声ファイルを文字起こしし、結果をテキストとして含む辞書を返す関数。
    JSON解析は行わず、APIからの応答テキストをそのまま'transcription'キーに格納する。
    """
    print(f"Geminiで文字起こし中: {file_path}")

    try:
        # Gemini APIを設定
        try:
            # 環境変数からAPIキーを取得（優先）
            api_key = os.environ.get("GEMINI_API_KEY")

            # 環境変数が設定されていない場合は設定ファイルから取得
            if not api_key:
                with open('settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    gemini_settings = settings.get('gemini', {})
                    api_key = gemini_settings.get("api_key")
                    model_name = gemini_settings.get("agent", "gemini-1.5-flash") # デフォルトモデルを更新
            else:
                # 設定ファイルからモデル名のみ取得
                try:
                    with open('settings.json', 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        gemini_settings = settings.get('gemini', {})
                        model_name = gemini_settings.get("agent", "gemini-1.5-flash")
                except:
                    model_name = "gemini-1.5-flash" # デフォルトモデル

            if not api_key or api_key == "YOUR_GEMINI_API_KEY":
                print("エラー: Gemini APIキーが設定されていません。環境変数GEMINI_API_KEYを設定するか、settings.jsonを更新してください。")
                return None
        except FileNotFoundError:
            print("エラー: settings.jsonファイルが見つかりません。")
            return None
        except json.JSONDecodeError:
            print("エラー: settings.jsonファイルの形式が正しくありません。")
            return None



        # 音声ファイルの情報を取得
        try:
            audio = AudioSegment.from_file(file_path)
            duration_seconds = len(audio) / 1000.0 # floatにする
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
        except FileNotFoundError:
            print(f"エラー: 音声ファイルが見つかりません: {file_path}")
            return None
        except Exception as e: # pydubのエラーなど
             print(f"エラー: 音声ファイルの読み込みに失敗しました: {e}")
             return None

        prompt = load_prompt("PROMPT\\transcription_prompt.md")

        print(f"音声ファイルを読み込み中: {file_path}")
        try:
            try:
                # 音声ファイルを読み込む
                with open(file_path, "rb") as f:
                    audio_data = f.read()

                # ファイル拡張子からMIMEタイプを判断
                file_ext = os.path.splitext(file_path)[1].lower()
                mime_type = "audio/mpeg"  # デフォルト
                if file_ext == ".wav":
                    mime_type = "audio/wav"
                elif file_ext == ".mp3":
                    mime_type = "audio/mpeg"
                elif file_ext == ".aac":
                    mime_type = "audio/aac"
                elif file_ext == ".m4a":
                    mime_type = "audio/mp4"
                # 修正しないでください
                # これで動きます
                print("Gemini APIにリクエスト中...")
                client = genai.Client(api_key=api_key)
                my_file = client.files.upload(file=file_path)
                # ビデオは、使用する前に処理する必要があります。
                while my_file.state.name == "PROCESSING":
                    print("ビデオを処理中...",end="\r")
                    time.sleep(5)
                    my_file = client.files.get(name=my_file.name)
                print()
                start_time = time.time()
                response = generate_content_with_retry(
                    client, model_name, [my_file, prompt]
                )
                if response is None:
                    print("Gemini APIからの応答の取得に失敗しました。")
                    return None

                response_text = response.text
                end_time = time.time()
                print(f"文字起こし完了。処理時間: {end_time - start_time:.2f} 秒")

                print("--- Geminiからの応答テキスト ---")
                print(response_text)
                print("--- --- ---")

                result = {
                    "transcription": response_text
                }
                return result

            except Exception as e:
                print(f"エラー: 音声ファイルの処理またはGemini APIへの送信中にエラーが発生しました: {e}")
                return None
        except FileNotFoundError:
            print(f"エラー: 音声ファイルが見つかりません: {file_path}")
            return None
        except Exception as e:
            print(f"エラー: 音声ファイルの読み込み中にエラーが発生しました: {e}")
            return None

    except FileNotFoundError:
        print(f"エラー: 設定ファイル 'settings.json' が見つかりません。")
        return None
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル 'settings.json' のJSON解析に失敗しました。")
        return None
    except Exception as e:
        print(f"エラー: Gemini設定中に予期せぬエラーが発生しました: {e}")
        return None


def transcribe_audio(file_path, server_url):
    """音声ファイルパスを文字起こしサーバーに送り、結果を取得する関数"""
    print(f"文字起こし中: {file_path}")

    try:
        payload = {"file_path": file_path}
        response = requests.post(server_url, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"エラー: サーバーがステータスコード {response.status_code} を返しました")
            print(f"レスポンス: {response.text}")
            return None
    except Exception as e:
        print(f"文字起こし中にエラーが発生しました: {str(e)}")
        return None

def check_hallucination_with_gemini(file_path: str, transcription: str) -> dict | None:
    """
    Gemini APIを使用して音声ファイルの文字起こし結果にハルシネーション（幻聴）がないかチェックする関数。
    音声ファイルと文字起こし結果を比較し、ハルシネーションの有無を判定する。
    """
    print(f"Geminiでハルシネーションチェック中: {file_path}")

    try:
        # Gemini APIを設定
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            gemini_settings = settings.get('gemini', {})
            api_key = os.environ.get("GEMINI_API_KEY") or gemini_settings.get("api_key")
            model_name = gemini_settings.get("agent", "gemini-1.5-flash") # デフォルトモデル

        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            print("エラー: Gemini APIキーが設定されていません。環境変数GEMINI_API_KEYを設定するか、settings.jsonを更新してください。")
            return None

        # 音声ファイルの情報を取得
        try:
            audio = AudioSegment.from_file(file_path)
            duration_seconds = len(audio) / 1000.0 # floatにする
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
        except FileNotFoundError:
            print(f"エラー: 音声ファイルが見つかりません: {file_path}")
            return None
        except Exception as e: # pydubのエラーなど
             print(f"エラー: 音声ファイルの読み込みに失敗しました: {e}")
             return None

        # プロンプトファイルを読み込み、変数を置換
        prompt_template = load_prompt("PROMPT\\hallucination_check_prompt.md")
        prompt = prompt_template.replace("{transcription}", transcription)

        print(f"音声ファイルを読み込み中: {file_path}")
        try:
            try:
                # 音声ファイルを読み込む
                with open(file_path, "rb") as f:
                    audio_data = f.read()

                # ファイル拡張子からMIMEタイプを判断
                file_ext = os.path.splitext(file_path)[1].lower()
                mime_type = "audio/mpeg"  # デフォルト
                if file_ext == ".wav":
                    mime_type = "audio/wav"
                elif file_ext == ".mp3":
                    mime_type = "audio/mpeg"
                elif file_ext == ".aac":
                    mime_type = "audio/aac"
                elif file_ext == ".m4a":
                    mime_type = "audio/mp4"

                print("Gemini APIにリクエスト中...")
                client = genai.Client(api_key=api_key)
                my_file = client.files.upload(file=file_path)
                # ビデオは、使用する前に処理する必要があります。
                while my_file.state.name == "PROCESSING":
                    print("ビデオを処理中...",end="\r")
                    time.sleep(5)
                    my_file = client.files.get(name=my_file.name)
                print()
                start_time = time.time()
                response = generate_content_with_retry(
                    client, model_name, [my_file, prompt]
                )
                if response is None:
                    print("Gemini APIからの応答の取得に失敗しました。")
                    return None

                response_text = response.text
                end_time = time.time()
                print(f"ハルシネーションチェック完了。処理時間: {end_time - start_time:.2f} 秒")

                print("--- Geminiからの応答テキスト ---")
                print(response_text)
                print("--- --- ---")

                # ハルシネーションの有無を判定
                has_hallucination = False
                if response_text is not None:
                    has_hallucination = "あり" in response_text.split("ハルシネーション:")[-1].strip()

                result = {
                    "hallucination_check": response_text,
                    "has_hallucination": has_hallucination
                }
                return result

            except Exception as e:
                print(f"エラー: 音声ファイルの処理またはGemini APIへの送信中にエラーが発生しました: {e}")
                return None
        except FileNotFoundError:
            print(f"エラー: 音声ファイルが見つかりません: {file_path}")
            return None
        except Exception as e:
            print(f"エラー: 音声ファイルの読み込み中にエラーが発生しました: {e}")
            return None

    except FileNotFoundError:
        print(f"エラー: 設定ファイル 'settings.json' が見つかりません。")
        return None
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル 'settings.json' のJSON解析に失敗しました。")
        return None
    except Exception as e:
        print(f"エラー: Gemini設定中に予期せぬエラーが発生しました: {e}")
        return None

def combine_transcriptions(transcriptions, chunk_times=None):
    """複数の文字起こし結果を1つに結合する関数

    この関数は、複数のチャンクに分割された音声ファイルの文字起こし結果を1つに結合します。
    Gemini APIの応答には'segments'キーが含まれていない場合があるため、存在チェックを行います。

    Args:
        transcriptions: 文字起こし結果のリスト。各要素は辞書で、'transcription'キーを含む。
                       'segments'キーが含まれている場合は、タイムスタンプ情報も結合されます。
        chunk_times: チャンクごとの実際の開始時間と終了時間のリスト [(start_time, end_time), ...]

    Returns:
        dict: 結合された文字起こし結果。'transcription'キーと'segments'キーを含む。
              'segments'キーは、元の文字起こし結果に'segments'キーが含まれていない場合は空のリストになります。
    """
    if not transcriptions:
        return None

    combined = {
        'transcription': '',
        'segments': []
    }

    # セグメントの時間オフセットを管理
    time_offset = 0

    for i, trans in enumerate(transcriptions):
        if not trans:
            continue

        # 文字起こしテキストを追加
        if combined['transcription']:
            combined['transcription'] += ' ' + trans['transcription']
        else:
            combined['transcription'] = trans['transcription']

        # チャンクの実際の開始時間が指定されている場合は、それを使用
        if chunk_times and i < len(chunk_times):
            # 前のチャンクとの時間差を計算
            if i > 0 and i-1 < len(chunk_times):
                # 現在のチャンクの開始時間 - 前のチャンクの終了時間
                time_gap = chunk_times[i][0] - chunk_times[i-1][1]
                # 時間差が負の場合（重複している場合）は0に設定
                time_gap = max(0, time_gap)
            else:
                # 最初のチャンクの場合は時間差なし
                time_gap = 0

            # 最初のチャンクの場合は、指定された開始時間を使用
            if i == 0:
                time_offset = chunk_times[i][0]
            else:
                # 2つ目以降のチャンクは、前のチャンクの終了時間 + 時間差
                time_offset = chunk_times[i-1][1] + time_gap

        # セグメントのタイムスタンプを調整して結合結果に追加
        # Gemini APIの応答には'segments'キーが含まれていない場合があるため、存在チェックを行う
        if 'segments' in trans and trans['segments']:
            for segment in trans['segments']:
                adjusted_segment = segment.copy()

                # チャンクの実際の開始時間が指定されている場合
                if chunk_times and i < len(chunk_times):
                    # セグメントの相対時間を計算（チャンク内での位置）
                    relative_start = segment['start']
                    relative_end = segment['end']

                    # チャンクの開始時間を基準に絶対時間を計算
                    adjusted_segment['start'] = chunk_times[i][0] + relative_start
                    adjusted_segment['end'] = chunk_times[i][0] + relative_end

                    # 終了時間がチャンクの終了時間を超えないように調整
                    adjusted_segment['end'] = min(adjusted_segment['end'], chunk_times[i][1])
                else:
                    # 従来の方法（時間オフセットを加算）
                    adjusted_segment['start'] += time_offset
                    adjusted_segment['end'] += time_offset

                combined['segments'].append(adjusted_segment)

            # 次のチャンク用に時間オフセットを更新（chunk_timesが指定されていない場合のみ）
            if not chunk_times and trans['segments']:
                last_segment = trans['segments'][-1]
                time_offset = last_segment['end']

    return combined


def is_video_file(file_path):
    """ファイルが動画ファイルかどうかを判定する関数"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    _, ext = os.path.splitext(file_path.lower())
    return ext in video_extensions

def is_audio_file(file_path):
    """ファイルが音声ファイルかどうかを判定する関数"""
    audio_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma']
    _, ext = os.path.splitext(file_path.lower())
    return ext in audio_extensions

def is_media_file(file_path):
    """ファイルがメディア（音声または動画）ファイルかどうかを判定する関数"""
    return is_video_file(file_path) or is_audio_file(file_path)

def get_media_files_in_folder(folder_path):
    """指定されたフォルダ内のすべてのメディアファイル（音声と動画）のパスを取得する関数"""
    media_files = []

    # フォルダが存在するか確認
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        print(f"エラー: フォルダ '{folder_path}' が見つかりません。")
        return media_files

    # フォルダ内のすべてのファイルを走査
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)

        # ファイルであり、メディアファイルであるかを確認
        if os.path.isfile(file_path) and is_media_file(file_path):
            media_files.append(file_path)

    return media_files

def process_video_with_gemini(file_path, prompt=None):
    """Gemini APIを使用して動画を処理し、内容を分析する関数"""
    if prompt is None:
        prompt = load_prompt("PROMPT\\video_analysis_prompt.md")
    print(f"Geminiで動画処理中: {file_path}")

    try:
        # Gemini APIを設定
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            gemini_settings = settings.get('gemini', {})
            api_key = os.environ.get("GEMINI_API_KEY") or gemini_settings.get("api_key")
            model_name = gemini_settings.get("agent", "gemini-2.0-flash")

        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            print("エラー: Gemini APIキーが設定されていません。環境変数GEMINI_API_KEYを設定するか、settings.jsonを更新してください。")
            return None


        client = genai.Client(api_key=api_key)
        start_time = time.time()
        # 動画ファイルをアップロード
        print(f"動画ファイルをアップロード中: {file_path}")
        uploaded_file = client.files.upload(file=file_path)
        print(f"アップロード完了: {uploaded_file.name}")

        # 動画の処理が完了するまで待機
        while uploaded_file.state.name == "PROCESSING":
            print("動画処理中...")
            time.sleep(5)
            uploaded_file = client.files.get(name=uploaded_file.name)

        print("動画処理完了")

        # 動画の内容を分析
        print(f"動画内容の分析中...")
        result = generate_content_with_retry(
            client, model_name, [uploaded_file, prompt]
        )

        if result is None:
            print("Gemini APIからの応答の取得に失敗しました。")
            return None

        print("--- Geminiからの応答テキスト ---")
        print(result.text)
        print("--- --- ---")

        return {
            "video_analysis": result.text
        }

    except Exception as e:
        print(f"エラー: 動画処理中にエラーが発生しました: {e}")
        return None

def process_media_file(file_path, analyze_video=False):
    """メディアファイルを処理し、適切な形式のファイルパスを返す関数"""
    # 動画ファイルかどうかを判定
    if is_video_file(file_path):
        print(f"動画ファイルを検出しました: {file_path}")

        # 動画内容の分析が指定されている場合
        if analyze_video:
            print("動画内容を分析します。")
            return file_path, True  # 動画分析フラグをTrueで返す

        # 動画が真っ暗かどうかを判定
        if is_video_dark(file_path):
            print("動画が真っ暗なため、AACオーディオに変換します。")
            # 動画からAACオーディオを抽出
            aac_path = convert_video_to_aac(file_path)
            if aac_path:
                return aac_path, False
            else:
                print("AACへの変換に失敗しました。元の動画ファイルを使用します。")
                return file_path, False
        else:
            print("動画は真っ暗ではないため、そのまま処理します。")
            return file_path, False
    else:
        # 動画ファイルでない場合はそのまま返す
        return file_path, False

def generate_summary(transcription):
    """Geminiを使って文字起こしの要約を生成する関数

    Args:
        transcription: 文字起こし結果の辞書（'transcription'キーを含む）

    Returns:
        str: 要約テキスト。エラーが発生した場合はエラーメッセージ。
    """
    try:
        # Gemini APIを設定
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            gemini_settings = settings.get('gemini', {})
            api_key = os.environ.get("GEMINI_API_KEY") or gemini_settings.get("api_key")
            model_name = gemini_settings.get("agent", "gemini-2.5-flash")

        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            print("エラー: Gemini APIキーが設定されていません。環境変数GEMINI_API_KEYを設定するか、settings.jsonを更新してください。")
            return "要約の生成中にエラーが発生しました。"

        # 要約生成用プロンプトを読み込み、変数を置換
        prompt_template = load_prompt("PROMPT\\summary_prompt.md")
        prompt = prompt_template.replace("{transcription}", transcription['transcription'])
        client = genai.Client(api_key=api_key)
        # ビデオは、使用する前に処理する必要があります。
        response = generate_content_with_retry(
            client, model_name, [prompt]
        )

        if response is None:
            print("Gemini APIからの応答の取得に失敗しました。")
            return "要約の生成中にエラーが発生しました。"

        # Geminiからの応答をpprintで出力
        print("Geminiからの要約応答:")
        pprint.pprint(response.text)

        return response.text
    except Exception as e:
        print(f"要約生成中にエラーが発生しました: {str(e)}")
        return "要約の生成中にエラーが発生しました。"

def generate_meeting_minutes(transcription, file_path):
    """Gemini 2.5 Flashを使って議事録を生成する関数

    Args:
        transcription: 文字起こし結果の辞書（'transcription'キーを含む）
        file_path: 音声ファイルのパス（授業情報の取得に使用）

    Returns:
        str: 生成された議事録テキスト。エラーが発生した場合はエラーメッセージ。
    """
    try:
        # Gemini APIを設定
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            gemini_settings = settings.get('gemini', {})
            api_key = os.environ.get("GEMINI_API_KEY") or gemini_settings.get("api_key")
            model_name = gemini_settings.get("agent", "gemini-2.5-flash")

        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            print("エラー: Gemini APIキーが設定されていません。環境変数GEMINI_API_KEYを設定するか、settings.jsonを更新してください。")
            return get_string('errors.minutes_generation')

        # モデルを作成
        #model = genai.GenerativeModel('gemini-2.5-flash')
        print("Gemini APIにリクエスト中...")
        client = genai.Client(api_key=api_key)

        # ファイル名から授業情報を取得
        class_info = get_class_info(file_path)

        # 議事録生成用プロンプトを読み込み、変数を置換
        # 授業変更があった場合は注記を追加
        class_change_note = "※この授業は急遽変更されました。" if class_info.get("changed", False) else ""

        prompt_template = load_prompt("PROMPT\\minutes_prompt_detailed.md")
        prompt = prompt_template.replace("{class_name}", class_info["name"])
        prompt = prompt.replace("{class_change_note}", class_change_note)
        prompt = prompt.replace("{datetime}", class_info.get("datetime", "[YYYY年MM月DD日 HH:MM～HH:MM]"))
        prompt = prompt.replace("{teacher}", class_info["teacher"])
        prompt = prompt.replace("{transcription}", transcription['transcription'])

        # 議事録を生成
        response = generate_content_with_retry(
            client, model_name, [prompt]
        )

        if response is None:
            print("Gemini APIからの応答の取得に失敗しました。")
            return get_string('errors.minutes_generation')

        # Geminiからの応答をpprintで出力
        print(get_string('info.gemini_minutes_response'))
        pprint.pprint(response.text)

        return response.text
    except Exception as e:
        print(get_string('errors.minutes_generation_detailed', error=str(e)))
        return get_string('errors.minutes_generation')

def main():
    parser = argparse.ArgumentParser(description=get_string('argparse.description'))
    parser.add_argument('--file', type=str, help=get_string('argparse.file'), 
                        default=None)
    parser.add_argument('--folder', type=str, help=get_string('argparse.folder'), 
                        default=None)
    parser.add_argument('--url', type=str, help=get_string('argparse.url'), 
                        default=None)
    parser.add_argument('--use-server', action='store_true', help=get_string('argparse.use_server'))
    parser.add_argument('--start-file', type=int, help=get_string('argparse.start_file'), default=0)
    parser.add_argument('--start-time', type=int, help=get_string('argparse.start_time'), default=0)
    parser.add_argument('--analyze-video', action='store_true', help=get_string('argparse.analyze_video'))
    parser.add_argument('--video-prompt', type=str, help=get_string('argparse.video_prompt'), 
                        default=get_string('prompts.video_analysis_file'))
    # Notionアップロード関連の引数
    parser.add_argument('--upload-notion', action='store_true', help=get_string('argparse.upload_notion'))
    parser.add_argument('--upload-notion-json', type=str, help=get_string('argparse.upload_notion_json'))
    parser.add_argument('--notion-parent', type=str, help=get_string('argparse.notion_parent'))
    parser.add_argument('--notion-token-file', type=str, help=get_string('argparse.notion_token_file'), default="settings.json")
    args = parser.parse_args()
    if args.file is None and args.folder is None and args.upload_notion_json is None:
        print(get_string('errors.no_file_specified'))
        exit(1)

    # JSONのみのアップロードモードかどうかを判定
    json_only_mode = args.file is None and args.folder is None and args.upload_notion_json is not None

    # フォルダモードかどうかを判定
    folder_mode = args.folder is not None

    if json_only_mode:
        print(get_string('info.json_upload_mode'))
        audio_file_path = None
        media_files = []
    elif folder_mode:
        print(get_string('info.folder_mode'))
        # フォルダパスを絶対パスに変換
        folder_path = os.path.abspath(args.folder)
        print(get_string('info.folder_path', folder_path=folder_path))

        # フォルダ内のすべてのメディアファイルを取得
        media_files = get_media_files_in_folder(folder_path)

        if not media_files:
            print(get_string('errors.no_media_files', folder_path=folder_path))
            exit(1)

        print(get_string('info.media_files_count', count=len(media_files)))
        for i, file_path in enumerate(media_files):
            print(f"  {i+1}. {os.path.basename(file_path)}")

        # 最初のファイルを処理するための設定
        audio_file_path = media_files[0]
    else:
        print(get_string('info.file_processing_start'))
        # 音声ファイルのパス
        audio_file_path = args.file
        # 絶対パスに変換
        audio_file_path = os.path.abspath(audio_file_path)
        print(get_string('info.audio_file', file_path=audio_file_path))
        media_files = [audio_file_path]

    # 文字起こし方法の決定
    use_server = args.use_server or args.url is not None
    if not json_only_mode:
        if use_server:
            if args.url is None:
                url = "http://localhost:5000/transcribe"
            else:
                url = args.url
            print(get_string('info.server_transcription', url=url))
        else:
            print(get_string('info.gemini_transcription'))

    try:
        # JSONのみのアップロードモードの場合は音声処理をスキップ
        if json_only_mode:
            print(get_string('info.json_upload_skip'))
        else:
            # フォルダモードまたは単一ファイルモードの場合、すべてのメディアファイルを処理
            for file_index, audio_file_path in enumerate(media_files):
                if len(media_files) > 1:
                    print(get_string('info.file_processing', current=file_index+1, total=len(media_files), filename=os.path.basename(audio_file_path)))

                # 音声処理とNotion JSONアップロードの変数を初期化
                combined_transcription = None
                original_file_path = None
                processed_file_path = None

                # ファイルの存在確認
                if not os.path.exists(audio_file_path):
                    print(get_string('errors.file_not_found', file_path=audio_file_path))
                    continue  # 次のファイルへ

                # 元のファイルパスを保存
                original_file_path = audio_file_path

                # メディアファイルを処理（動画の場合は必要に応じてAACに変換または分析）
                processed_file_path, is_video_analysis = process_media_file(audio_file_path, args.analyze_video)

                # 動画分析の場合
                if is_video_analysis:
                    print(get_string('info.video_analysis_mode'))
                    video_analysis = process_video_with_gemini(processed_file_path, args.video_prompt)

                    if video_analysis:
                        # 分析結果を表示
                        print(get_string('info.video_analysis_result'))
                        print(video_analysis['video_analysis'])

                        # 分析結果をファイル保存
                        base_name = os.path.splitext(os.path.basename(processed_file_path))[0]

                        # 出力ディレクトリの設定を読み込む
                        output_dir = "."  # デフォルトは現在のディレクトリ
                        try:
                            with open('settings.json', 'r', encoding='utf-8') as f:
                                settings = json.load(f)
                                if "output" in settings:
                                    if "txt_directory" in settings["output"]:
                                        output_dir = settings["output"]["txt_directory"]
                                    elif "directory" in settings["output"]:
                                        output_dir = settings["output"]["directory"]
                                    # ディレクトリが存在しない場合は作成
                                    if not os.path.exists(output_dir):
                                        os.makedirs(output_dir)
                        except Exception as e:
                            print(f"警告: 出力ディレクトリの設定の読み込みに失敗しました: {str(e)}")

                        # 出力ファイルのパスを生成
                        video_analysis_path = os.path.join(output_dir, f"{base_name}_video_analysis.txt")

                        with open(video_analysis_path, "w", encoding="utf-8") as f:
                            f.write(video_analysis['video_analysis'])

                        print(f"\n動画分析結果を {video_analysis_path} に保存しました。")
                        print("\nこのファイルの処理が完了しました。")
                    else:
                        print("エラー: 動画分析に失敗しました。")

                    # 動画分析モードの場合は次のファイルへ
                    continue

                # 処理後のファイルパスが元のパスと異なる場合（変換された場合）
                if processed_file_path != audio_file_path:
                    print(f"処理後のファイル: {processed_file_path}")
                    audio_file_path = processed_file_path

                # 音声の長さを取得
                duration = get_audio_duration(audio_file_path)
                print(f"音声の長さ: {duration:.2f}秒")

                # 40分（2400秒）を超える場合は分割
                if duration > 2400:
                    print("音声が40分を超えるため、分割して処理します。")

                    # ハルシネーション検出時の再試行のための変数
                    max_retries = 3
                    retry_count = 0
                    has_hallucination = True
                    combined_transcription = None

                    # ハルシネーションがなくなるか、最大再試行回数に達するまで繰り返す
                    while has_hallucination and retry_count <= max_retries:
                        if retry_count > 0:
                            print(f"\n=== ハルシネーションが検出されたため、文字起こしを再試行します（{retry_count}/{max_retries}）===")

                        # チャンク数を計算
                        num_chunks = math.ceil(duration / 2400)
                        # チャンクの長さを計算
                        chunk_duration = duration / num_chunks
                        print(f"分割数: {num_chunks}個")
                        print(f"チャンクサイズ: {chunk_duration:.2f}秒")

                        # 開始ファイル番号と開始時間を表示
                        if args.start_file > 0 or args.start_time > 0:
                            print(f"指定された開始ファイル番号: {args.start_file}")
                            print(f"指定された開始時間: {args.start_time}秒")

                        # 音声をチャンクに分割（開始ファイル番号と開始時間を指定）
                        chunk_info = split_audio(audio_file_path, chunk_duration, args.start_file, args.start_time)
                        print(f"{len(chunk_info)}個のチャンクに分割しました。")

                        # チャンクのパスと時間情報を分離
                        chunk_paths = []
                        chunk_times = []
                        for info in chunk_info:
                            chunk_paths.append(info[0])
                            chunk_times.append((info[1], info[2]))  # (start_time, end_time)

                        # 各チャンクを並列に文字起こし
                        transcriptions = [None] * len(chunk_paths)
                        chunk_files_to_delete = chunk_paths.copy()

                        # 文字起こし処理を行う関数
                        def process_chunk(index, chunk_path):
                            try:
                                print(f"チャンク {index+1}/{len(chunk_paths)} の文字起こしを開始します")
                                if use_server:
                                    trans = transcribe_audio(chunk_path, url)
                                else:
                                    trans = transcribe_audio_with_gemini(chunk_path)
                                print(f"チャンク {index+1}/{len(chunk_paths)} の文字起こしが完了しました")
                                return index, trans
                            except Exception as e:
                                print(f"チャンク {index+1}/{len(chunk_paths)} の文字起こし中にエラーが発生しました: {e}")
                                return index, None

                        # ThreadPoolExecutorを使用して並列処理
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            # 各チャンクの処理をスケジュール
                            future_to_index = {
                                executor.submit(process_chunk, i, chunk_path): i 
                                for i, chunk_path in enumerate(chunk_paths)
                            }

                            # 完了したタスクから結果を取得
                            for future in concurrent.futures.as_completed(future_to_index):
                                index, trans = future.result()
                                if trans:
                                    transcriptions[index] = trans

                        # 一時ファイルを削除
                        for chunk_path in chunk_files_to_delete:
                            try:
                                os.unlink(chunk_path)
                            except Exception as e:
                                print(f"一時ファイル {chunk_path} の削除中にエラーが発生しました: {e}")

                        # 文字起こし結果を結合（チャンクの時間情報を渡す）
                        combined_transcription = combine_transcriptions(transcriptions, chunk_times)

                        if not combined_transcription:
                            print("文字起こしに失敗しました。再試行を中止します。")
                            break

                        # 文字起こし結果を表示
                        print("\n=== 文字起こし結果 ===")
                        print(combined_transcription['transcription'])

                        # ハルシネーションチェックを実行
                        print("\nハルシネーションチェックを実行しています...")
                        hallucination_check = None
                        if not use_server:  # Gemini APIを使用している場合のみ
                            hallucination_check = check_hallucination_with_gemini(
                                audio_file_path, 
                                combined_transcription['transcription']
                            )

                        if hallucination_check:
                            print("\n=== ハルシネーションチェック結果 ===")
                            print(hallucination_check['hallucination_check'])

                            has_hallucination = hallucination_check['has_hallucination']

                            if has_hallucination:
                                print("\n警告: 文字起こしにハルシネーション（幻聴）が検出されました。")
                                if retry_count < max_retries:
                                    print(f"再度文字起こしを実行します。")
                                else:
                                    print(f"最大再試行回数（{max_retries}）に達しました。ハルシネーションが残っていますが処理を続行します。")
                            else:
                                print("\nハルシネーション（幻聴）は検出されませんでした。")
                        else:
                            print("ハルシネーションチェックに失敗しました。エラーが発生したため、ハルシネーションなしとして処理を続行します。")
                            # チェックに失敗した場合はループを抜ける
                            has_hallucination = False

                        retry_count += 1
                else:
                    print("音声が40分以下のため、分割せずに処理します。")

                    # ハルシネーション検出時の再試行のための変数
                    max_retries = 3
                    retry_count = 0
                    has_hallucination = True

                    # ハルシネーションがなくなるか、最大再試行回数に達するまで繰り返す
                    while has_hallucination and retry_count <= max_retries:
                        if retry_count > 0:
                            print(f"\n=== ハルシネーションが検出されたため、文字起こしを再試行します（{retry_count}/{max_retries}）===")

                        # ファイル全体を文字起こし
                        if use_server:
                            combined_transcription = transcribe_audio(audio_file_path, url)
                        else:
                            combined_transcription = transcribe_audio_with_gemini(audio_file_path)

                        if not combined_transcription:
                            print("文字起こしに失敗しました。再試行を中止します。")
                            break

                        # 文字起こし結果を表示
                        print("\n=== 文字起こし結果 ===")
                        print(combined_transcription['transcription'])

                        # ハルシネーションチェックを実行
                        print("\nハルシネーションチェックを実行しています...")
                        hallucination_check = None
                        if not use_server:  # Gemini APIを使用している場合のみ
                            hallucination_check = check_hallucination_with_gemini(
                                audio_file_path, 
                                combined_transcription['transcription']
                            )

                        if hallucination_check:
                            print("\n=== ハルシネーションチェック結果 ===")
                            print(hallucination_check['hallucination_check'])

                            has_hallucination = hallucination_check['has_hallucination']

                            if has_hallucination:
                                print("\n警告: 文字起こしにハルシネーション（幻聴）が検出されました。")
                                if retry_count < max_retries:
                                    print(f"再度文字起こしを実行します。")
                                else:
                                    print(f"最大再試行回数（{max_retries}）に達しました。ハルシネーションが残っていますが処理を続行します。")
                            else:
                                print("\nハルシネーション（幻聴）は検出されませんでした。")
                        else:
                            print("ハルシネーションチェックに失敗しました。エラーが発生したため、ハルシネーションなしとして処理を続行します。")
                            # チェックに失敗した場合はループを抜ける
                            has_hallucination = False

                        retry_count += 1

                if combined_transcription:

                    # 要約を生成
                    # Gemini APIを使用して文字起こし結果から要約を生成
                    # 注: Gemini APIの応答には'segments'キーが含まれていないため、combine_transcriptionsで対応
                    #print("\n要約を生成しています...")
                    #summary = generate_summary(combined_transcription)

                    #print("\n=== 要約 ===")
                    #print(summary)

                    # 議事録を生成
                    print("\n議事録を生成しています...")
                    minutes = generate_meeting_minutes(combined_transcription, audio_file_path)

                    print("\n=== 議事録 ===")
                    print(minutes)

                    # 文字起こしと議事録をファイル保存
                    base_name = os.path.splitext(os.path.basename(audio_file_path))[0]

                    # 出力ディレクトリの設定を読み込む
                    output_dir = "."  # デフォルトは現在のディレクトリ
                    try:
                        with open('settings.json', 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                            if "output" in settings:
                                if "txt_directory" in settings["output"]:
                                    output_dir = settings["output"]["txt_directory"]
                                elif "directory" in settings["output"]:
                                    output_dir = settings["output"]["directory"]
                                # ディレクトリが存在しない場合は作成
                                if not os.path.exists(output_dir):
                                    os.makedirs(output_dir)
                    except Exception as e:
                        print(f"警告: 出力ディレクトリの設定の読み込みに失敗しました: {str(e)}")

                    # 出力ファイルのパスを生成
                    transcription_path = os.path.join(output_dir, f"{base_name}_transcription.txt")
                    minutes_path = os.path.join(output_dir, f"{base_name}_minutes.txt")

                    with open(transcription_path, "w", encoding="utf-8") as f:
                        f.write(combined_transcription['transcription'])
                    with open(minutes_path, "w", encoding="utf-8") as f:
                        f.write(minutes)

                    # ハルシネーションチェック結果を保存
                    if hallucination_check:
                        hallucination_check_path = os.path.join(output_dir, f"{base_name}_hallucination_check.txt")
                        with open(hallucination_check_path, "w", encoding="utf-8") as f:
                            f.write(hallucination_check['hallucination_check'])
                        print(f"\n文字起こし結果を {transcription_path} に保存しました。")
                        print(f"要約を {os.path.join(output_dir, f'{base_name}_summary.txt')} に保存しました。")
                        print(f"議事録を {minutes_path} に保存しました。")
                        print(f"ハルシネーションチェック結果を {hallucination_check_path} に保存しました。")
                    else:
                        print(f"\n文字起こし結果を {transcription_path} に保存しました。")
                        print(f"要約を {os.path.join(output_dir, f'{base_name}_summary.txt')} に保存しました。")
                        print(f"議事録を {minutes_path} に保存しました。")

                    # Notionへのアップロード処理
                    if args.upload_notion:
                        notion_parent = args.notion_parent
                        if not notion_parent:
                            # settings.jsonからデータベースIDを取得
                            try:
                                with open('settings.json', 'r', encoding='utf-8') as f:
                                    settings = json.load(f)
                                    if "notion" in settings and "database_id" in settings["notion"]:
                                        notion_parent = settings["notion"]["database_id"]
                                        print(f"settings.jsonからNotionデータベースID '{notion_parent}' を取得しました。")
                                    else:
                                        print("エラー: settings.jsonにNotion database_idが設定されていません。")
                            except Exception as e:
                                print(f"エラー: settings.jsonの読み込みに失敗しました: {str(e)}")

                        if not notion_parent:
                            print("エラー: Notionにアップロードするには --notion-parent オプションでページまたはデータベースIDを指定してください。")
                        else:
                            try:
                                # NotionUploaderのインスタンスを作成
                                # settings.jsonをデフォルトとして使用
                                uploader = NotionUploader(settings_file="settings.json")

                                print(f"\n議事録をNotionにアップロードしています...")

                                # 議事録をアップロード
                                result = uploader.upload_lecture_note_from_file(notion_parent, minutes_path)

                                # 結果の表示
                                if result["success"]:
                                    print(f"成功: {result['message']}")
                                    print(f"ページURL: {result['url']}")
                                else:
                                    print(f"失敗: {result['message']}")
                            except Exception as e:
                                print(f"Notionへのアップロード中にエラーが発生しました: {str(e)}")

                    # 一時的なAACファイルを削除
                    if processed_file_path != original_file_path and os.path.exists(processed_file_path):
                        try:
                            os.remove(processed_file_path)
                            print(f"一時ファイル {processed_file_path} を削除しました。")
                        except Exception as e:
                            print(f"一時ファイルの削除中にエラーが発生しました: {str(e)}")

                    print(f"\nファイル {file_index+1}/{len(media_files)} の処理が完了しました。")
                else:
                    print("エラー: 文字起こしに失敗しました。")

        # JSONファイルのNotionアップロード処理（音声処理とは別）
        if args.upload_notion_json is not None:
            notion_parent = args.notion_parent
            if not notion_parent:
                # settings.jsonからデータベースIDを取得
                try:
                    with open('settings.json', 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        if "notion" in settings and "database_id" in settings["notion"]:
                            notion_parent = settings["notion"]["database_id"]
                            print(f"settings.jsonからNotionデータベースID '{notion_parent}' を取得しました。")
                        else:
                            print("エラー: settings.jsonにNotion database_idが設定されていません。")
                except Exception as e:
                    print(f"エラー: settings.jsonの読み込みに失敗しました: {str(e)}")

            if not notion_parent:
                print("エラー: Notionにアップロードするには --notion-parent オプションでページまたはデータベースIDを指定してください。")
            else:
                try:
                    # NotionUploaderのインスタンスを作成
                    # settings.jsonをデフォルトとして使用
                    uploader = NotionUploader(settings_file="settings.json")

                    json_file_path = args.upload_notion_json
                    print(f"\n講義ノートをJSON形式でNotionにアップロードしています...")
                    print(f"JSONファイル: {json_file_path}")

                    # JSONファイルの存在確認
                    if not os.path.exists(json_file_path):
                        print(f"エラー: 指定されたJSONファイル '{json_file_path}' が見つかりません。")
                    else:
                        # JSONファイルをアップロード
                        result = uploader.upload_lecture_note_from_json(notion_parent, json_file_path)

                        # 結果の表示
                        if result["success"]:
                            print(f"成功: {result['message']}")
                            print(f"ページURL: {result['url']}")
                        else:
                            print(f"失敗: {result['message']}")
                except Exception as e:
                    print(f"Notionへのアップロード中にエラーが発生しました: {str(e)}")

        print("\n処理が完了しました。")

    except Exception as e:
        print(f"エラー: 予期しない問題が発生しました: {str(e)}")

if __name__ == "__main__":
    main()
