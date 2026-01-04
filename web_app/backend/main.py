import sys
import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 添加 DeepSeek-OCR-hf 路径以便加载模型
# 注意：现在的路径是 web_app/backend/main.py，所以需要向上两级
PROJECT_ROOT = Path(__file__).parent.parent.parent
HF_PATH = PROJECT_ROOT / "DeepSeek-OCR-master" / "DeepSeek-OCR-hf"
sys.path.append(str(HF_PATH))

# 尝试导入 transformers 和 torch
try:
    import torch
    from transformers import AutoModel, AutoTokenizer
except ImportError:
    print("Error: Missing dependencies. Please run 'pip install -r requirements.txt'")
    sys.exit(1)

# 模型路径配置
MODEL_PATH = os.environ.get("DEEPSEEK_OCR_MODEL_PATH", str(PROJECT_ROOT / "model"))

# 全局变量
model = None
tokenizer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer
    print(f"Loading model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print(f"Warning: Model path {MODEL_PATH} does not exist. Please download the model and place it in the 'model' directory, or set DEEPSEEK_OCR_MODEL_PATH.")
    else:
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
            
            # 准备模型加载参数
            model_kwargs = {
                "trust_remote_code": True,
                "use_safetensors": True,
                "_attn_implementation": 'eager'
            }

            # 显存优化逻辑
            if torch.cuda.is_available():
                # 检查 bitsandbytes 是否可用（用于 4-bit 量化）
                try:
                    from transformers import BitsAndBytesConfig
                    import bitsandbytes as bnb
                    print("BitsAndBytes detected. Enabling 4-bit quantization for memory optimization...")
                    
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    model_kwargs["quantization_config"] = quantization_config
                    model_kwargs["device_map"] = "auto"
                except ImportError:
                    print("Warning: bitsandbytes not found. 4-bit quantization is NOT available.")
                    print("Falling back to bfloat16 with device_map='auto'. This may require >14GB VRAM.")
                    model_kwargs["device_map"] = "auto"
                    model_kwargs["torch_dtype"] = torch.bfloat16
            else:
                print("CUDA not available. Loading on CPU (Performance will be limited).")
                model_kwargs["torch_dtype"] = torch.float32

            # 加载模型
            model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
            print("Model loaded successfully.")
            
        except Exception as e:
            print(f"Failed to load model: {e}")
            import traceback
            traceback.print_exc()
    
    yield
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan, title="DeepSeek-OCR Web App")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
@app.post("/api/ocr")
async def ocr_endpoint(file: UploadFile = File(...), mode: str = Form("markdown")):
    global model, tokenizer
    if model is None:
        if not os.path.exists(MODEL_PATH):
             raise HTTPException(status_code=503, detail="Model not loaded and model path not found.")
        # 如果模型存在但加载失败，尝试重新加载的逻辑可以在这里添加，或者直接报错
        raise HTTPException(status_code=503, detail="Model not loaded properly. Check server logs.")

    # 保存上传的文件
    temp_dir = PROJECT_ROOT / "temp_uploads"
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 准备 prompt
        if mode == "markdown":
            prompt = "<image>\n<|grounding|>Convert the document to markdown. "
        elif mode == "ocr":
            prompt = "<image>\nFree OCR."
        else:
            prompt = "<image>\n<|grounding|>Convert the document to markdown. "
            
        # 调用模型进行预测
        # 注意：需要适配 DeepSeek-OCR 的调用方式
        # 这里假设模型对象有类似 generate 或 chat 的方法，或者我们需要使用 helper
        # 根据 easy_ocr.py，通常是:
        # result = model.chat(tokenizer, image_path, prompt) 
        # 但这里的 model 是 AutoModel 加载的，可能只是一个 transformer model
        # 让我们查看 DeepSeek-OCR-hf/easy_ocr.py 了解正确的调用方式
        
        # 假设 model 是 DeepseekOCRModel (因为 trust_remote_code=True)
        # 通常自定义模型会有 .chat 或 .generate 方法封装
        # 让我们假设它有 chat 方法，如果报错再修复
        
        # 临时修复：使用 hasattr 检查
        if hasattr(model, 'chat'):
            response = model.chat(tokenizer, str(file_path), prompt)
        elif hasattr(model, 'generate'):
             # 如果没有 chat 方法，可能需要手动处理 inputs
             # 这里先保留原来的逻辑假设，或者抛出更详细的错误
             raise HTTPException(status_code=500, detail="Model does not support 'chat' method.")
        else:
             raise HTTPException(status_code=500, detail="Unknown model interface.")

        return JSONResponse(content={"result": response})
        
    except Exception as e:
        print(f"Error during OCR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if file_path.exists():
            try:
                os.remove(file_path)
            except:
                pass

# 挂载前端静态文件 (生产环境)
# 只有在 dist 目录存在时才挂载
DIST_DIR = PROJECT_ROOT / "web_app" / "frontend" / "dist"
if os.path.exists(DIST_DIR):
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
else:
    @app.get("/")
    async def read_root():
        return {"message": "Frontend not built. Please run 'npm run build' in web_app/frontend."}
