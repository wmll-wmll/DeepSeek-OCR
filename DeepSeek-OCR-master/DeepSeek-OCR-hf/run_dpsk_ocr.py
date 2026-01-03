from transformers import AutoModel, AutoTokenizer
import torch
import os
import ssl

# Hack to bypass SSL verification for Hugging Face download
os.environ['CURL_CA_BUNDLE'] = ''
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

os.environ["CUDA_VISIBLE_DEVICES"] = '0'


model_name = r'../../model'


tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
# Windows support: switch to sdpa or eager instead of flash_attention_2
model = AutoModel.from_pretrained(model_name, _attn_implementation='eager', trust_remote_code=True, use_safetensors=True)
model = model.eval().cuda().to(torch.bfloat16)



# prompt = "<image>\nFree OCR. "
prompt = "<image>\n<|grounding|>Convert the document to markdown. "
# Use an example image from assets
image_file = r'../../assets/show1.jpg'
output_path = r'../../output'

if not os.path.exists(output_path):
    os.makedirs(output_path)



# infer(self, tokenizer, prompt='', image_file='', output_path = ' ', base_size = 1024, image_size = 640, crop_mode = True, test_compress = False, save_results = False):

# Tiny: base_size = 512, image_size = 512, crop_mode = False
# Small: base_size = 640, image_size = 640, crop_mode = False
# Base: base_size = 1024, image_size = 1024, crop_mode = False
# Large: base_size = 1280, image_size = 1280, crop_mode = False

# Gundam: base_size = 1024, image_size = 640, crop_mode = True

res = model.infer(tokenizer, prompt=prompt, image_file=image_file, output_path = output_path, base_size = 1024, image_size = 640, crop_mode=True, save_results = True, test_compress = True)
