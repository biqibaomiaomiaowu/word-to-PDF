import asyncio
import os
import sys
import json
import subprocess
from typing import Optional
from ..core.logger import logger


def _decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


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
        from ..utils.paddle_runtime import build_paddle_env, get_paddle_python_path
        python_exe = get_paddle_python_path()

        if not python_exe or not os.path.exists(python_exe):
            raise Exception("未找到独立的 Paddle 环境 (.paddle_env) 或指定路径不正确，请确保环境配置正确。")

        # Use the structured PPStructureV3 runner for complex-layout recovery.
        runner_script = os.path.join(os.path.dirname(__file__), "run_paddle_structure_v4.py")
        paddle_env = build_paddle_env()
        crash_return_codes = {3221225477, -1073741819}

        def _run_runner(device: str | None, disable_formula: bool = False):
            cmd = [
                python_exe,
                runner_script,
                "--input", input_path,
                "--output_dir", output_dir
            ]
            if device:
                cmd.extend(["--device", device])
            if disable_formula:
                cmd.append("--disable-formula")
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3600,
                env=paddle_env,
            )

        def _convert():
            logger.info(f"Starting PaddleOCR subprocess for {input_path} -> {output_dir}")

            try:
                attempts: list[tuple[str | None, bool]] = [(None, False), ("cpu", False), ("cpu", True)]
                result = None
                for index, (device, disable_formula) in enumerate(attempts):
                    result = _run_runner(device, disable_formula=disable_formula)
                    if result.returncode not in crash_return_codes:
                        break
                    if index < len(attempts) - 1:
                        logger.warning(
                            "Paddle subprocess crashed with native return code %s. Retrying with device=%s disable_formula=%s.",
                            result.returncode,
                            attempts[index + 1][0] or "auto",
                            attempts[index + 1][1],
                        )

                # We expect the last line (or all of stdout) to be a JSON string
                assert result is not None
                output_str = _decode_output(result.stdout).strip()
                stderr_str = _decode_output(result.stderr).strip()
                json_start = output_str.rfind("{")
                json_end = output_str.rfind("}")

                if result.returncode != 0 and json_start == -1:
                    logger.error(f"Paddle subprocess failed with return code {result.returncode}. Stderr: {stderr_str}")
                    raise Exception(f"复杂版面引擎崩溃: {stderr_str}")

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
