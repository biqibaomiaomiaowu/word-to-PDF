import argparse
import sys
import os
import json
import traceback

# ======== 核心修复：避开 Windows 中文用户名导致的 Paddle C++ 底层路径截断 Bug ========
# 强制将 Paddle 和 PaddleX 的模型下载/缓存目录指向当前项目内的隐藏文件夹
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
os.environ["PADDLE_HOME"] = os.path.join(WORKSPACE_ROOT, ".paddle_models")
os.environ["PADDLEX_HOME"] = os.path.join(WORKSPACE_ROOT, ".paddlex_models")
os.environ["PADDLE_INFERENCE_MODEL_DIR"] = os.path.join(WORKSPACE_ROOT, ".paddle_inference")
# 彻底欺骗 Python 的 os.path.expanduser("~") 避免老版本写死 C盘
os.environ["USERPROFILE"] = WORKSPACE_ROOT
os.environ["HOME"] = WORKSPACE_ROOT
# ==============================================================================================

import fitz
import numpy as np
import cv2

def run_paddle_ocr(input_path, output_dir):
    try:
        import paddle
        from paddleocr import PaddleOCR
        import docx
        from docx.shared import Pt
    except ImportError as e:
        return {"success": False, "error": f"Failed to import PaddleOCR or docx: {e}"}

    filename = os.path.basename(input_path)
    name, _ = os.path.splitext(filename)
    output_filepath = os.path.join(output_dir, f"{name}.docx")
    temp_dir = os.path.join(output_dir, f"paddle_temp_{name}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Determine GPU availability dynamically
        use_gpu = False
        try:
            use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.get_device() != 'cpu'
        except Exception:
            pass
            
        import paddleocr
        device_str = 'gpu' if use_gpu else 'cpu'
        if getattr(paddleocr, '__version__', '').startswith('3.'):
            engine = PaddleOCR(
                lang='ch',
                device=device_str,
                use_doc_orientation_classify=False,
                use_textline_orientation=False,
                use_doc_unwarping=False,
                text_detection_model_name='PP-OCRv4_server_det',
                text_recognition_model_name='PP-OCRv4_server_rec'
            )
        else:
            engine = PaddleOCR(
                use_angle_cls=False,
                lang='ch',
                use_gpu=use_gpu,
                show_log=False
            )

        doc = fitz.open(input_path)
        merged_doc = docx.Document()

        for page_num in range(doc.page_count):
            if page_num > 0:
                merged_doc.add_page_break()
                
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

            if pix.n == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif pix.n == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

            result = engine.ocr(img_array)
            
            # Simple fallback to dump text line by line to a word document
            if result and len(result) > 0 and result[0]:
                for line in result[0]:
                    # line 通常类似于: [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ('Text', confidence)]
                    # Paddle 3.x / PaddleX 返回结构发生变化，为了安全，我们需要做容错解包
                    try:
                        if len(line) == 2 and isinstance(line[1], (list, tuple)):
                            text, conf = line[1]
                            p = merged_doc.add_paragraph(text)
                        elif len(line) == 2 and isinstance(line[0], str):  # 有些时候会直接返回 (text, conf)
                            text, conf = line[0], line[1]
                            p = merged_doc.add_paragraph(text)
                        elif isinstance(line, dict) and 'text' in line:
                            p = merged_doc.add_paragraph(line['text'])
                        else:
                            # 终极 fallback，尽力提取文本
                            p = merged_doc.add_paragraph(str(line))
                    except Exception as print_ex:
                        # 忽略单行错误
                        pass
                    
        doc.close()
        merged_doc.save(output_filepath)

        # Cleanup
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        return {
            "success": True,
            "output_path": output_filepath,
            "converter_used": "paddle"
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": f"Exception during PaddleOCR processing: {str(e)}", "traceback": traceback.format_exc()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input PDF path")
    parser.add_argument("--output_dir", required=True, help="Output directory path")
    args = parser.parse_args()

    result = run_paddle_ocr(args.input, args.output_dir)
    print(json.dumps(result))
