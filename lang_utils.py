import os
import json

class LangUtils:
    """
    Utility class for loading and accessing language strings.
    """

    def __init__(self, settings_file="settings.json"):
        """
        Initialize the language utility with the specified settings file.

        Args:
            settings_file (str): Path to the settings file containing language configuration.
        """
        self.settings_file = settings_file
        self.lang_dir = "lang"
        self.default_lang = "ja"
        self.strings = {}
        self.load_language()

    def load_settings(self):
        """
        Load settings from the settings file.

        Returns:
            dict: The settings dictionary.
        """
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            return {}

    def load_language(self):
        """
        Load language strings based on the settings.
        """
        settings = self.load_settings()
        lang_code = settings.get("app", {}).get("language", self.default_lang)

        lang_file = os.path.join(self.lang_dir, f"{lang_code}.json")

        # If the language file doesn't exist, fall back to the default language
        if not os.path.exists(lang_file):
            print(f"Language file {lang_file} not found, falling back to {self.default_lang}")
            lang_file = os.path.join(self.lang_dir, f"{self.default_lang}.json")

        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
                print(f"Loaded language file: {lang_file}")
        except Exception as e:
            print(f"Error loading language file {lang_file}: {str(e)}")
            self.strings = {}

    def get(self, key, **kwargs):
        """
        Get a language string by key with optional format arguments.

        Args:
            key (str): The key of the language string, using dot notation (e.g., "errors.file_not_found").
            **kwargs: Format arguments to replace placeholders in the string.

        Returns:
            str: The formatted language string, or the key itself if not found.
        """
        # Split the key by dots to navigate the nested dictionary
        parts = key.split('.')
        current = self.strings

        # Navigate through the nested dictionary
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Key not found, return the original key
                return key

        # If we found a string, format it with the provided arguments
        if isinstance(current, str):
            # Check if the string is a file path to a prompt file
            if current.startswith("PROMPT\\") and os.path.exists(current):
                try:
                    with open(current, 'r', encoding='utf-8') as f:
                        prompt_content = f.read()
                    try:
                        return prompt_content.format(**kwargs)
                    except KeyError as e:
                        print(f"Missing format argument in prompt file '{current}': {str(e)}")
                        return prompt_content
                    except Exception as e:
                        print(f"Error formatting prompt file '{current}': {str(e)}")
                        return prompt_content
                except Exception as e:
                    print(f"Error reading prompt file '{current}': {str(e)}")
                    return current
            else:
                try:
                    return current.format(**kwargs)
                except KeyError as e:
                    print(f"Missing format argument in string '{key}': {str(e)}")
                    return current
                except Exception as e:
                    print(f"Error formatting string '{key}': {str(e)}")
                    return current

        # If we didn't find a string, return the original key
        return key

# Create a singleton instance for easy access
lang = LangUtils()

# Function to get a language string (shorthand for lang.get)
def get_string(key, **kwargs):
    """
    Get a language string by key with optional format arguments.

    Args:
        key (str): The key of the language string, using dot notation (e.g., "errors.file_not_found").
        **kwargs: Format arguments to replace placeholders in the string.

    Returns:
        str: The formatted language string, or the key itself if not found.
    """
    return lang.get(key, **kwargs)
