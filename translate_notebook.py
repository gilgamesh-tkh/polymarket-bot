import json
import sys
import urllib.parse
import urllib.request
import time

def translate_text(text, target='fr'):
    """Translate text using MyMemory API."""
    if not text.strip():
        return text
    # MyMemory API: https://mymemory.translated.net/doc/spec.php
    url = "https://api.mymemory.translated.net/get"
    params = {
        'q': text,
        'langpair': f'en|{target}'
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    try:
        with urllib.request.urlopen(full_url) as response:
            data = json.load(response)
            translated = data['responseData']['translatedText']
            # If translation failed, return original
            if translated == '' or translated is None:
                return text
            return translated
    except Exception as e:
        print(f"Translation error: {e}", file=sys.stderr)
        return text

def translate_notebook(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown':
            # Join source lines, translate, then split back
            source = ''.join(cell['source'])
            translated = translate_text(source)
            # Ensure we end with newline if original did?
            # Split by newline to keep list format
            cell['source'] = translated.splitlines(keepends=True)
            # If the original ended with a newline, ensure last element ends with newline?
            # We'll just keep as is.
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python translate_notebook.py <input.ipynb> <output.ipynb>")
        sys.exit(1)
    translate_notebook(sys.argv[1], sys.argv[2])