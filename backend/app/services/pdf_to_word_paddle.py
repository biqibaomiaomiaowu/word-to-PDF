import asyncio
import os
import sys
import json
import subprocess
from typing import Optional
from ..core.logger import logger

class PDFToWordPaddleService:
    @staticmethod
    async def convert_to_word(input_path: str, output_dir: str) -> str:
        """
        Converts a complex layout PDF file to a DOCX file by invoking an external
        PaddleOCR subprocess from the independent `.paddle_env`.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Find the independent .paddle_env Python executable
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        paddle_env_dir = os.path.join(base_dir, ".paddle_env")

        if sys.platform.startswith("win"):
            python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(paddle_env_dir, "bin", "python")

        if not os.path.exists(python_exe):
            raise Exception("未找到独立的 Paddle 环境 (.paddle_env)，请确保环境配置正确。")

        # The runner script
        runner_script = os.path.join(os.path.dirname(__file__), "run_paddle_ocr.py")

        def _convert():
            logger.info(f"Starting PaddleOCR subprocess for {input_path} -> {output_dir}")

            cmd = [
                python_exe,
                runner_script,
                "--input", input_path,
                "--output_dir", output_dir
            ]

            try:
                # Run the subprocess and capture the output
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )

                # We expect the last line (or all of stdout) to be a JSON string
                output_str = result.stdout.strip()
                json_start = output_str.rfind("{")
                json_end = output_str.rfind("}")

                if result.returncode != 0 and json_start == -1:
                    logger.error(f"Paddle subprocess failed with return code {result.returncode}. Stderr: {result.stderr}")
                    raise Exception(f"复杂版面引擎崩溃: {result.stderr}")

                if json_start != -1 and json_end != -1:
                    json_str = output_str[json_start:json_end+1]
                    try:
                        parsed_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse subprocess output as JSON: {json_str}. Error: {e}")
                        raise Exception("无法解析复杂版面引擎的输出结果。")

                    if parsed_result.get("success"):
                        output_filepath = parsed_result.get("output_path")
                        if not output_filepath or not os.path.exists(output_filepath):
                            raise Exception("引擎报告成功，但未找到输出文件。")
                        logger.info(f"PaddleOCR subprocess completed successfully: {output_filepath}")
                        return output_filepath
                    else:
                        error_msg = parsed_result.get("error", "未知错误")
                        logger.error(f"Paddle subprocess returned error: {error_msg}")
                        raise Exception(f"复杂版面恢复失败: {error_msg}")
                else:
                    logger.error(f"Paddle subprocess output did not contain JSON: {output_str}")
                    raise Exception("复杂版面引擎输出了非预期格式的数据。")

            except subprocess.TimeoutExpired:
                logger.error(f"Paddle subprocess timed out for {input_path}")
                raise Exception("复杂版面引擎处理超时 (已超过 1 小时)。")
            except Exception as e:
                logger.error(f"Exception calling Paddle subprocess: {e}", exc_info=True)
                raise e

        # Run synchronous subprocess conversion in a thread pool
        try:
            output_filepath = await asyncio.to_thread(_convert)
            return output_filepath
        except Exception as e:
            logger.error(f"Error during PDF to Word conversion (Paddle subprocess): {e}", exc_info=True)
            raise e
