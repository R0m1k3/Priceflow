import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
import app.core.search_config
print(f"Search Config File: {app.core.search_config.__file__}")
from app.core.search_config import SITE_CONFIGS
print(f"Keys: {list(SITE_CONFIGS.keys())}")

with open(app.core.search_config.__file__, 'r') as f:
    content = f.read()
    print(f"File content length: {len(content)}")
    print(f"Contains stokomani.fr: {'stokomani.fr' in content}")
