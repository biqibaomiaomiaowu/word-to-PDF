from app.models.schemas import ConversionType, ConverterMode
from app.utils.converter_modes import (
    build_invalid_converter_mode_message,
    get_supported_converter_modes,
    is_converter_mode_supported,
)


def test_supported_converter_modes_for_word_to_pdf():
    supported = get_supported_converter_modes(ConversionType.WORD_TO_PDF)
    assert supported == (
        ConverterMode.AUTO,
        ConverterMode.LIBREOFFICE,
        ConverterMode.WORD,
    )


def test_supported_converter_modes_for_pdf_to_word():
    supported = get_supported_converter_modes(ConversionType.PDF_TO_WORD)
    assert supported == (
        ConverterMode.AUTO,
        ConverterMode.PDF2DOCX,
        ConverterMode.PADDLE,
    )


def test_invalid_converter_mode_message_mentions_supported_modes():
    message = build_invalid_converter_mode_message(
        ConversionType.WORD_TO_PDF,
        ConverterMode.PADDLE,
    )
    assert "word_to_pdf" in message
    assert "paddle" in message
    assert "libreoffice" in message
    assert "word" in message


def test_converter_mode_support_rejects_cross_direction_modes():
    assert not is_converter_mode_supported(ConversionType.WORD_TO_PDF, ConverterMode.PADDLE)
    assert not is_converter_mode_supported(ConversionType.PDF_TO_WORD, ConverterMode.WORD)
