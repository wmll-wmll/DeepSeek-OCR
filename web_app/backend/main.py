import sys
import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# 添加 DeepSeek-OCR-hf 路径以便加载模型
PROJECT_ROOT = Path(__file__).parent.parent
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
# 默认假设模型在项目根目录的 model 文件夹
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
                model = model.eval().to(torch.float32) # CPU通常不支持bfloat16
                print("Model loaded on CPU. This might be slow.")
        except Exception as e:
            print(f"Failed to load model: {e}")
    
    yield
    
    # Clean up if needed
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan, title="DeepSeek-OCR Web App")

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/ocr")
async def ocr_endpoint(file: UploadFile = File(...), mode: str = Form("markdown")):
    global model, tokenizer
    if model is None:
        # 如果模型未加载，尝试动态加载（方便测试，如果路径后来才准备好）
        # 但在生产环境中应该在启动时加载
        if not os.path.exists(MODEL_PATH):
             raise HTTPException(status_code=503, detail="Model not loaded and model path not found.")
    
    if model is None or tokenizer is None:
         raise HTTPException(status_code=503, detail="Model not loaded properly.")

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
        # infer 方法通常会将结果写入文件，并返回生成的文本
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
        
        # 如果 res 是 None 或者空，尝试读取生成的 markdown 文件
        content = res
        if not content:
            # 推测生成的文件名
            # 通常是 图片名 + .md (或者是 _ocr.md 等)
            # 这里需要查看具体实现，或者简单地搜索最新生成的文件
            # 假设文件名保持不变，只是扩展名变为 .md
            # 但为了准确性，我们直接返回 res，如果为空前端提示
            pass

        return JSONResponse(content={"result": content, "file_name": file.filename})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 可以选择删除临时文件
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
