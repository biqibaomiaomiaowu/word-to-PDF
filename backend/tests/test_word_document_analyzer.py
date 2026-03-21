from app.utils.word_document_analyzer import analyze_word_document


class FakeZipArchive:
    def __init__(self, mapping):
        self.mapping = mapping

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def namelist(self):
        return list(self.mapping)

    def read(self, name):
        if name not in self.mapping:
            raise KeyError(name)
        return self.mapping[name].encode("utf-8")


def test_analyze_word_document_detects_omml_and_axmath(monkeypatch):
    monkeypatch.setattr(
        "app.utils.word_document_analyzer.ZipFile",
        lambda _: FakeZipArchive(
            {
                "word/document.xml": (
                    '<w:document>'
                    '<m:oMath></m:oMath>'
                    '<w:object><o:OLEObject ProgID="Equation.AxMath"/></w:object>'
                    '</w:document>'
                ),
                "word/settings.xml": '<m:mathPr><m:mathFont m:val="Cambria Math"/></m:mathPr>',
            }
        ),
    )

    report = analyze_word_document("formula.docx")

    assert report.has_formula_risk is True
    assert "detected 1 OMML formulas" in report.reasons
    assert "detected 1 AxMath objects" in report.reasons
    assert "detected Cambria Math font usage" in report.reasons
    assert report.stats["omml_count"] == 1
    assert report.stats["axmath_count"] == 1
    assert report.stats["uses_cambria_math"] is True


def test_analyze_word_document_plain_docx_is_not_risky(monkeypatch):
    monkeypatch.setattr(
        "app.utils.word_document_analyzer.ZipFile",
        lambda _: FakeZipArchive(
            {
                "word/document.xml": "<w:document><w:p>Hello</w:p></w:document>",
            }
        ),
    )

    report = analyze_word_document("plain.docx")

    assert report.has_formula_risk is False
    assert report.reasons == []


def test_analyze_word_document_marks_doc_as_high_risk():
    report = analyze_word_document("legacy.doc")

    assert report.has_formula_risk is True
    assert report.reasons == ["detected legacy .doc input"]



def test_analyze_word_document_scans_header_parts(monkeypatch):
    monkeypatch.setattr(
        "app.utils.word_document_analyzer.ZipFile",
        lambda _: FakeZipArchive(
            {
                "word/document.xml": "<w:document><w:p>Hello</w:p></w:document>",
                "word/header1.xml": '<w:hdr><m:oMath></m:oMath></w:hdr>',
            }
        ),
    )

    report = analyze_word_document("header-formula.docx")

    assert report.has_formula_risk is True
    assert "detected 1 OMML formulas" in report.reasons
    assert report.stats["parts_scanned"] == 2
