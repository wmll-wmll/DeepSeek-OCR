import os
import shutil
import site
import sys
from pathlib import Path

def fix_bitsandbytes():
    print("Checking bitsandbytes installation for CUDA 12.4 compatibility...")
    
    # 查找 site-packages
    site_packages = site.getsitepackages()
    bnb_path = None
    for p in site_packages:
        possible_path = Path(p) / "bitsandbytes"
        if possible_path.exists():
            bnb_path = possible_path
            break
            
    if not bnb_path:
        print("Error: bitsandbytes not found in site-packages.")
        return

    print(f"Found bitsandbytes at: {bnb_path}")
    
    # 查找 dll 目录
    # 在某些版本中，dll 可能直接在 bitsandbytes 目录下，或者在 lib 目录下，或者在 bin 目录下
    # 根据用户日志: E:\github\DeepSeek-OCR\.venv\lib\site-packages\bitsandbytes\libbitsandbytes_cuda124.dll
    # 看来它直接在包根目录下找
    
    # 常见的 dll 名称
    dll_names = list(bnb_path.glob("libbitsandbytes_cuda*.dll"))
    if not dll_names:
        print("No CUDA DLLs found in bitsandbytes directory.")
        return
        
    print(f"Found DLLs: {[d.name for d in dll_names]}")
    
    # 目标 dll
    target_dll_name = "libbitsandbytes_cuda124.dll"
    target_dll = bnb_path / target_dll_name
    
    if target_dll.exists():
        print(f"{target_dll_name} already exists. No action needed.")
        return
        
    # 寻找最佳的源 dll (优先找 12x, 然后 11x)
    source_dll = None
    
    # 尝试找 121, 122, 120 等
    for ver in ["123", "122", "121", "120", "118", "117"]:
        candidate = bnb_path / f"libbitsandbytes_cuda{ver}.dll"
        if candidate.exists():
            source_dll = candidate
            break
            
    if not source_dll:
        # 如果没有特定版本，找任何一个 cuda dll
        source_dll = dll_names[0]
        
    print(f"Copying {source_dll.name} to {target_dll_name}...")
    try:
        shutil.copy2(source_dll, target_dll)
        print("Success! CUDA 12.4 support patched.")
    except Exception as e:
        print(f"Failed to copy DLL: {e}")

if __name__ == "__main__":
    fix_bitsandbytes()
