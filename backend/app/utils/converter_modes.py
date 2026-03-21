from __future__ import annotations

from ..models.schemas import ConversionType, ConverterMode


PDF_TO_WORD_MODES = (
    ConverterMode.AUTO,
    ConverterMode.PDF2DOCX,
    ConverterMode.PADDLE,
)

WORD_TO_PDF_MODES = (
    ConverterMode.AUTO,
    ConverterMode.LIBREOFFICE,
    ConverterMode.WORD,
)


def get_supported_converter_modes(conversion_type: ConversionType) -> tuple[ConverterMode, ...]:
    if conversion_type == ConversionType.PDF_TO_WORD:
        return PDF_TO_WORD_MODES
    if conversion_type == ConversionType.WORD_TO_PDF:
        return WORD_TO_PDF_MODES
    return (ConverterMode.AUTO,)


def is_converter_mode_supported(
    conversion_type: ConversionType,
    converter_mode: ConverterMode,
) -> bool:
    return converter_mode in get_supported_converter_modes(conversion_type)


def build_invalid_converter_mode_message(
    conversion_type: ConversionType,
    converter_mode: ConverterMode,
) -> str:
    supported = ", ".join(mode.value for mode in get_supported_converter_modes(conversion_type))
    return (
        f"Converter mode '{converter_mode.value}' is not supported for "
        f"conversion type '{conversion_type.value}'. Supported modes: {supported}."
    )
