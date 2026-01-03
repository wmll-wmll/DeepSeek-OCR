import os
import ssl
import urllib3
import requests
from huggingface_hub import snapshot_download

# Use HF mirror
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey patch ssl to ignore verification
_create_unverified_https_context = ssl._create_unverified_context
ssl._create_default_https_context = _create_unverified_https_context

# Monkey patch requests to ignore verify=True
old_request = requests.Session.request
def new_request(self, method, url, *args, **kwargs):
    kwargs['verify'] = False
    return old_request(self, method, url, *args, **kwargs)
requests.Session.request = new_request

print("Starting download from hf-mirror.com with SSL verification disabled...")
try:
    snapshot_download(repo_id="deepseek-ai/DeepSeek-OCR", ignore_patterns=["*.msgpack", "*.h5", "*.ot"], resume_download=True)
    print("Download completed successfully!")
except Exception as e:
    print(f"Download failed: {e}")
