from dotenv import load_dotenv
import os
from pathlib import Path

# Load .flaskenv before importing app
load_dotenv('.flaskenv')

from app import app

if __name__ == "__main__":
    # Collect all template and static files for auto-reload
    extra_files = []

    # Add all HTML templates
    templates_dir = Path('app/templates')
    if templates_dir.exists():
        for template_file in templates_dir.rglob('*.html'):
            extra_files.append(str(template_file))

    # Add all CSS files
    static_dir = Path('app/static')
    if static_dir.exists():
        for css_file in static_dir.rglob('*.css'):
            extra_files.append(str(css_file))
        for js_file in static_dir.rglob('*.js'):
            extra_files.append(str(js_file))

    app.run(
        port=5030,
        debug=True,
        extra_files=extra_files
    )
