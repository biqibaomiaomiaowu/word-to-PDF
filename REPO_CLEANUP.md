# Repo Cleanup Notes

## Active entrypoints to keep

- `start_all.py`
- `scripts/start_all_bootstrap_v2.py`
- `backend/app/services/pdf_to_word_paddle.py`
- `backend/app/services/run_paddle_structure_v4.py`
- `backend/app/utils/paddle_runtime.py`
- `check_paddle_env.py`
- `check_paddle_env_v2.py`
- `scripts/download_ppstructure_models.ps1`
- `scripts/test_ppstructure_conversion_v3.py`

## Compatibility wrappers currently kept

- `scripts/test_ppstructure_conversion.py`
- `scripts/test_ppstructure_conversion_v2.py`

These now delegate to `scripts/test_ppstructure_conversion_v3.py`.

## Old implementation files that are likely removable after confirmation

- `scripts/start_all_bootstrap.py`
- `backend/app/services/run_paddle_structure_v3.py`
- `backend/app/services/run_paddle_ocr_v2.py`

## Generated files and cache directories that should be removed later

- `.cache/ppstructure_download.py`
- `.cache/tmp/`
- `.paddlex_tmp/`
- `tmp_structure_test/`
- `tmp_structure_out/`
- `tmp_probe_pages/`
- `temp_ppstructure_download.py`
- `dev_output.log`
- `frontend_dev.log`
- `npm_install.log`
- `start_all.log`
- `start_dev.log`
- `fake.pdf`
- `test.txt`
- root-level random 8-character files such as `00hy03wn`
- accidental runtime directories at repo root:
  - `AppData/`
  - `Microsoft/`
  - `pip/`
  - `backend/pip/`

## Current formula/layout status

- Main runner is `run_paddle_structure_v4.py`
- Table and image object recovery is working
- Inline formula OMML generation is partially working
- Latest known sample result:
  - `xml_tables: 30`
  - `xml_drawings: 5`
  - `xml_omath: 37`
