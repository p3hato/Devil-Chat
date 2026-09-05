import json
import os
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'devil_config.json')

DEFAULT_CONFIG: Dict[str, Any] = {
    'language': 'en',
    'default_username': '',
    'default_color': 'Red'
}

def load_config() -> Dict[str, Any]:
    """
    Loads non-identifying local user preferences.
    If the configuration file does not exist, returns defaults (English).
    Does NOT store messages or permanent IDs.
    """
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return DEFAULT_CONFIG.copy()
            if 'language' not in data or not isinstance(data['language'], str):
                data['language'] = 'en'
            return data
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> bool:
    """Saves non-identifying preferences to devil_config.json."""
    try:
        safe_data = {
            'language': str(config.get('language', 'en')),
            'default_username': str(config.get('default_username', ''))[:16],
            'default_color': str(config.get('default_color', 'Red'))
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(safe_data, f, indent=2)
        return True
    except Exception:
        return False
