# Audio Transcription and Minutes Generation Tool

This tool transcribes audio files and automatically generates meeting minutes using Gemini 2.5 Flash. For audio files longer than 40 minutes, it splits them into chunks for processing to improve transcription accuracy.

## Main Features

- Audio file transcription using Gemini 2.5 Flash
- Option to use a local transcription server (traditional method)
- Automatic splitting of audio files longer than 40 minutes
- Automatic meeting minutes generation using Gemini 2.5 Flash
- Saving transcription results and minutes as text files
- Support for video files, with automatic conversion of dark videos to AAC audio
- Ability to specify sudden class changes in filenames (reflected in minutes)

## Requirements

- Python 3.6 or higher
- Gemini API key (required for transcription and minutes generation)
- Notion API token (optional, required for uploading to Notion)
- OpenCV and NumPy (installed via requirements.txt)
- (Optional) Local transcription server running at http://localhost:5000/transcribe (required for traditional transcription method)

## Installation
1. Copy Note
   https://highfalutin-gooseberry-12c.notion.site/1e2270a9eb668054a2a8eebfc65224fb?v=1e2270a9eb668196aa27000c0e349b08
2. Clone this repository
3. Install required packages

```bash
pip install -r requirements.txt
```

4. Set API keys as environment variables

```bash
# For Windows
set GEMINI_API_KEY=your_gemini_api_key_here
set NOTION_TOKEN=your_notion_token_here
set NOTION_DATABASE_ID=your_notion_database_id_here

# For Linux/Mac
export GEMINI_API_KEY=your_gemini_api_key_here
export NOTION_TOKEN=your_notion_token_here
export NOTION_DATABASE_ID=your_notion_database_id_here
```

5. Prepare the settings file

Copy settings.json.example to settings.json and configure the necessary information.
If environment variables are set, they take precedence.

```bash
# For Windows
copy settings.json.example settings.json

# For Linux/Mac
cp settings.json.example settings.json
```

Edit the settings.json file to configure class schedule information, output directories, etc.
It is recommended to set API keys and tokens using environment variables.

## Usage

Run the script by specifying the path to an audio or video file. By default, it uses Gemini 2.5 Flash for transcription.

```bash
python upload_and_transcribe.py --file path/to/audio_file.mp3
```

It also supports video files.

```bash
python upload_and_transcribe.py --file path/to/video_file.mp4
```

To use a local transcription server, specify the --use-server option.

```bash
python upload_and_transcribe.py --file path/to/media_file.mp3 --use-server
```

To change the URL of the transcription server, specify the --url option.
(Specifying the --url option automatically uses server-based transcription)

```bash
python upload_and_transcribe.py --file path/to/media_file.mp3 --url http://server:port/endpoint
```

### Specifying Start Position for Split Files

When processing long audio files, you can start processing from a specific file number or time.

To start processing from a specific file number (0-based):

```bash
python upload_and_transcribe.py --file path/to/audio_file.mp3 --start-file 2
```

To start processing from a specific time (in seconds):

```bash
python upload_and_transcribe.py --file path/to/audio_file.mp3 --start-time 1800
```

You can also combine both:

```bash
python upload_and_transcribe.py --file path/to/audio_file.mp3 --start-file 1 --start-time 600
```

## Operation Overview

1. Determine if the input file is video or audio
2. For video files:
   - Check 4 spots in the frame to analyze if it's dark
   - If dark, extract audio and convert to AAC format
   - If not dark, process as is
3. Get the length of the audio/video
4. If longer than 40 minutes (2400 seconds):
   - Calculate the number of chunks (ceiling of duration/2400)
   - Split the audio into equal-length chunks
   - If a start file number (--start-file) and start time (--start-time) are specified, start processing from that position
   - Transcribe each chunk individually (default: Gemini 2.5 Flash, optional: local server)
   - Record the actual start and end times of each chunk
   - Combine transcription results (timestamps adjusted based on actual start times)
5. If 40 minutes or less, transcribe the entire file at once (default: Gemini 2.5 Flash, optional: local server)
6. After transcription, generate minutes using Gemini 2.5 Flash
7. Save transcription results and minutes as text files

## Uploading to Notion

You can upload transcribed minutes to Notion.

```bash
# Upload minutes to Notion
python upload_and_transcribe.py --file path/to/media_file.mp3 --upload-notion --notion-parent your_notion_database_id

# Upload a JSON file to Notion
python upload_to_notion.py --file path/to/minutes.json --parent your_notion_database_id
```

For uploading to Notion, you need to set the environment variables `NOTION_TOKEN` and `NOTION_DATABASE_ID` or configure them in the settings.json file.

## Multi-language Support

This tool supports multiple languages. Currently, the following languages are supported:

- Japanese (ja) - Default
- English (en)

To change the language setting, edit the `app.language` parameter in the `settings.json` file:

```json
"app": {
  "language": "ja"  // "ja" (Japanese) or "en" (English)
}
```

To add a new language, create a new language file (e.g., `fr.json`) in the `lang` directory and add translations following the structure of existing language files.

## Notes

- The transcription server must accept an absolute path via the `file_path` key and return JSON containing `transcription` (transcription text) and `segments` (detailed information)
- For video files, it automatically detects dark videos (e.g., audio recordings with black screens) and converts them to AAC audio for processing
- Non-dark videos are processed as is
- For sudden class changes, include "変更_new_class_name" in the filename (e.g., "3限_変更_特別講義.mp3") to reflect the new class name and change note in the minutes
- Do not commit API keys or tokens to the repository. Use environment variables or add configuration files to .gitignore.
