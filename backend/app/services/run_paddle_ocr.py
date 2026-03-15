import argparse
import sys
import os
import json
import traceback
import fitz
import numpy as np
import cv2

def run_paddle_ocr(input_path, output_dir):
    try:
        import paddle
        from paddleocr import PPStructure, save_structure_res
        import docx
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

        engine = PPStructure(
            show_log=False,
            recovery=True,
            lang='ch',
            use_gpu=use_gpu,
            layout=True,
            table=True,
            ocr=True
        )

        doc = fitz.open(input_path)
        generated_docx_paths = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

            if pix.n == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif pix.n == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

            result = engine(img_array)

            save_folder = os.path.join(temp_dir, f"page_{page_num}")
            os.makedirs(save_folder, exist_ok=True)
            img_name = f"page_{page_num}"

            save_structure_res(result, save_folder, img_name)
            page_docx_path = os.path.join(save_folder, f"{img_name}_recovery.docx")

            if os.path.exists(page_docx_path):
                generated_docx_paths.append(page_docx_path)

        doc.close()

        if not generated_docx_paths:
            return {"success": False, "error": "No pages were successfully recovered by PaddleOCR."}

        merged_doc = docx.Document(generated_docx_paths[0])
        for path in generated_docx_paths[1:]:
            if not os.path.exists(path):
                continue
            merged_doc.add_page_break()
            sub_doc = docx.Document(path)
            for element in sub_doc.element.body:
                if element.tag.endswith('sectPr'):
                    continue
                merged_doc.element.body.append(element)

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
