import argparse
import os
import torch
from transformers import AutoModel, AutoTokenizer
from transformers.generation import GenerationConfig
import sys

# 设置默认模型路径 (相对于当前脚本)
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../model"))

def main():
    parser = argparse.ArgumentParser(description="DeepSeek-OCR 简易运行工具")
    parser.add_argument("--image", type=str, required=True, help="图片路径")
    parser.add_argument("--output", type=str, default=None, help="输出目录 (默认为 output)")
    parser.add_argument("--mode", type=str, default="markdown", choices=["ocr", "markdown", "figure", "rec"], help="模式: ocr (纯文本), markdown (格式化), figure (图表), rec (定位)")
    parser.add_argument("--query", type=str, default="", help="自定义查询 (仅在高级模式下需要)")
    
    args = parser.parse_args()

    # 检查图片是否存在
    if not os.path.exists(args.image):
        print(f"错误: 找不到图片文件: {args.image}")
        sys.exit(1)

    # 设置输出目录
    if args.output is None:
        args.output = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output"))
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    print(f"正在加载模型，路径: {MODEL_PATH} ...")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        # Windows 优化: 使用 eager 模式
        model = AutoModel.from_pretrained(MODEL_PATH, _attn_implementation='eager', trust_remote_code=True, use_safetensors=True)
        model = model.eval().cuda().to(torch.bfloat16)
    except Exception as e:
        print(f"模型加载失败: {e}")
        print("请确保已正确下载模型并在支持 CUDA 的环境中运行。")
        sys.exit(1)

    print("模型加载完成，开始推理...")

    # 构建 Prompt
    if args.query:
        prompt = f"<image>\n{args.query}"
    elif args.mode == "markdown":
        prompt = "<image>\n<|grounding|>Convert the document to markdown. "
    elif args.mode == "ocr":
        prompt = "<image>\nFree OCR."
    elif args.mode == "figure":
        prompt = "<image>\nParse the figure."
    elif args.mode == "rec":
        prompt = "<image>\nLocate the content." # 示例，实际可能需要更具体的指令
    else:
        prompt = "<image>\n<|grounding|>Convert the document to markdown. "

    print(f"Prompt: {prompt.strip()}")

    try:
        # 调用推理
        # infer 参数: tokenizer, prompt, image_file, output_path, base_size=1024, image_size=640, crop_mode=True, save_results=True, test_compress=True
        res = model.infer(
            tokenizer, 
            prompt=prompt, 
            image_file=args.image, 
            output_path=args.output, 
            base_size=1024, 
            image_size=640, 
            crop_mode=True, 
            save_results=True, 
            test_compress=False # 设为 False 可能更快一点，或者 True 也没关系
        )
        
        print("-" * 30)
        print("推理完成！")
        print(f"结果已保存到: {args.output}")
        print("-" * 30)
        
    except Exception as e:
        print(f"推理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
