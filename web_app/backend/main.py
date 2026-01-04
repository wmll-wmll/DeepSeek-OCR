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
loading_error = None  # 用于存储加载过程中的错误信息

import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer, loading_error
    print(f"Loading model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        error_msg = f"Model path {MODEL_PATH} does not exist. Please download the model."
        print(f"Warning: {error_msg}")
        loading_error = error_msg
    else:
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
            
            # 基础模型参数
            model_kwargs = {
                "trust_remote_code": True,
                "use_safetensors": True,
                "_attn_implementation": 'eager'
            }

            # 显存优化逻辑 (带自动回退)
            if torch.cuda.is_available():
                try:
                    # 尝试启用 4-bit 量化
                    from transformers import BitsAndBytesConfig
                    import bitsandbytes as bnb
                    print("BitsAndBytes detected. Attempting to enable 4-bit quantization...")
                    
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    model_kwargs["quantization_config"] = quantization_config
                    model_kwargs["device_map"] = "auto"
                    
                    # 尝试加载模型（如果在这一步 bnb 报错，会触发异常并进入回退逻辑）
                    print("Loading model with Quantization...")
                    model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
                    print("Model loaded successfully with 4-bit Quantization.")
                    
                except Exception as e:
                    print(f"Warning: Quantization failed ({str(e)}).")
                    print("Falling back to standard loading with device_map='auto' (managed by accelerate).")
                    print("This may use system RAM if VRAM is insufficient.")
                    
                    # 重置参数，移除量化配置
                    model_kwargs = {
                        "trust_remote_code": True,
                        "use_safetensors": True,
                        "_attn_implementation": 'eager',
                        "device_map": "auto",
                        "torch_dtype": torch.bfloat16
                    }
                    
                    # 再次尝试加载
                    model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
                    print("Model loaded successfully with Fallback settings.")
            else:
                print("CUDA not available. Loading on CPU (Performance will be limited).")
                model_kwargs["torch_dtype"] = torch.float32
                model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
                print("Model loaded successfully on CPU.")
            
        except Exception as e:
            loading_error = str(e)
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
    global model, tokenizer, loading_error
    
    if model is None:
        detail_msg = "Model not loaded."
        if loading_error:
            detail_msg += f" Error: {loading_error}"
        elif not os.path.exists(MODEL_PATH):
            detail_msg += " Model path not found."
        else:
            detail_msg += " Check server logs for details."
            
        raise HTTPException(status_code=503, detail=detail_msg)

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
        if hasattr(model, 'infer'):
            # 创建唯一的临时输出目录
            request_id = str(uuid.uuid4())
            temp_output_dir = PROJECT_ROOT / "temp_outputs" / request_id
            temp_output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                print(f"Calling model.infer with save_results=True, output_dir={temp_output_dir}...")
                
                # model.infer 会根据输入文件名生成输出文件名
                # 例如输入 test.jpg，输出可能是 test.md 或 test.txt
                input_filename_stem = file_path.stem
                
                res = model.infer(
                    tokenizer, 
                    prompt=prompt, 
                    image_file=str(file_path), 
                    output_path=str(temp_output_dir), 
                    base_size=1024, 
                    image_size=640, 
                    crop_mode=True, 
                    save_results=True, 
                    test_compress=False
                )
                
                print(f"model.infer returned: {type(res)}")
                
                # 尝试读取输出文件
                output_content = ""
                
                # 查找生成的文件
                generated_files = list(temp_output_dir.glob("*"))
                print(f"Generated files: {generated_files}")
                
                if generated_files:
                    # 优先找 .md
                    md_files = [f for f in generated_files if f.suffix.lower() == '.md']
                    if md_files:
                        target_file = md_files[0]
                    else:
                        # 否则取第一个文件
                        target_file = generated_files[0]
                        
                    print(f"Reading result from: {target_file}")
                    with open(target_file, "r", encoding="utf-8") as f:
                        output_content = f.read()
                
                # 如果没读到文件内容，尝试使用返回值
                if not output_content and isinstance(res, str):
                    output_content = res
                    
                if not output_content:
                    output_content = "OCR completed but no output content could be retrieved."
                    
                response = output_content

            except Exception as e:
                print(f"Error in model.infer: {e}")
                raise e
            finally:
                # 清理临时目录
                try:
                    shutil.rmtree(temp_output_dir)
                except Exception as cleanup_error:
                    print(f"Failed to cleanup temp dir {temp_output_dir}: {cleanup_error}")
                
        elif hasattr(model, 'chat'):
            response = model.chat(tokenizer, str(file_path), prompt)
        elif hasattr(model, 'generate'):
             # 如果没有 chat 方法，可能需要手动处理 inputs
             raise HTTPException(status_code=500, detail="Model does not support 'chat' method.")
        else:
             print(f"Model type: {type(model)}")
             print(f"Model attributes: {dir(model)}")
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
DIST_DIR = PROJECT_ROOT / "web_app" / "frontend" / "dist"
if os.path.exists(DIST_DIR):
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
else:
    @app.get("/")
    async def read_root():
        return {"message": "Frontend not built. Please run 'npm run build' in web_app/frontend."}
