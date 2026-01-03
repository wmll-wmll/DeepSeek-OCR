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
            # Windows 优化: 使用 eager 模式
            model = AutoModel.from_pretrained(MODEL_PATH, _attn_implementation='eager', trust_remote_code=True, use_safetensors=True)
            
            if torch.cuda.is_available():
                model = model.eval().cuda().to(torch.bfloat16)
                print("Model loaded on CUDA.")
            else:
                model = model.eval().to(torch.float32)
                print("Model loaded on CPU. This might be slow.")
        except Exception as e:
            print(f"Failed to load model: {e}")
    
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
    
    if model is None or tokenizer is None:
         # 尝试重新加载（仅用于调试）
         pass 
         # raise HTTPException(status_code=503, detail="Model not loaded properly.")

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
            
        # 设置输出目录
        output_path = PROJECT_ROOT / "output"
        output_path.mkdir(exist_ok=True)
        
        # 运行推理
        if model:
            res = model.infer(
                tokenizer,
                prompt=prompt,
                image_file=str(file_path),
                output_path=str(output_path),
                base_size=1024,
                image_size=640,
                crop_mode=True,
                save_results=True,
                test_compress=False
            )
            content = res
        else:
            # Mock for testing without model
            content = f"Mock Result: Model not loaded. File saved at {file_path}"

        return JSONResponse(content={"result": content, "file_name": file.filename})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 可以选择删除临时文件
        pass

# 挂载前端静态文件 (如果存在构建产物)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    print("Warning: Frontend build not found. API only mode.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
