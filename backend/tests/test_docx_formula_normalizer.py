from zipfile import ZipInfo

from app.services.docx_formula_normalizer import DocxFormulaNormalizer


WORD_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<w:document
    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    xmlns:v="urn:schemas-microsoft-com:vml"
    xmlns:o="urn:schemas-microsoft-com:office:office">
  <w:body>
    <w:p>
      <w:r>
        <w:object>
          <v:shape id="_x0000_i1025" o:ole="t">
            <v:imagedata r:id="rIdPreview" o:title=""/>
          </v:shape>
          <o:OLEObject Type="Embed" ProgID="Equation.AxMath" r:id="rIdOle"/>
        </w:object>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""


WORD_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdOle" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/oleObject1.bin"/>
  <Relationship Id="rIdPreview" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.wmf"/>
</Relationships>
"""


class FakeReadZipArchive:
    def __init__(self, mapping):
        self.mapping = mapping

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def namelist(self):
        return list(self.mapping)

    def read(self, name):
        return self.mapping[name]

    def infolist(self):
        return [ZipInfo(name) for name in self.mapping]


class FakeWriteZipArchive:
    def __init__(self):
        self.written = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def writestr(self, info, data):
        name = info.filename if hasattr(info, "filename") else info
        self.written[name] = data


def test_flatten_axmath_objects_to_preview_images(monkeypatch):
    input_path = "D:/input.docx"
    output_path = "D:/output.docx"
    read_mapping = {
        "[Content_Types].xml": b"<Types></Types>",
        "word/document.xml": WORD_DOCUMENT_XML.encode("utf-8"),
        "word/_rels/document.xml.rels": WORD_DOCUMENT_RELS.encode("utf-8"),
        "word/embeddings/oleObject1.bin": b"ole",
        "word/media/image1.wmf": b"preview",
    }
    write_archive = FakeWriteZipArchive()

    def fake_zipfile(path, mode="r", compression=None):
        if mode == "w":
            assert path == output_path
            return write_archive
        assert path == input_path
        return FakeReadZipArchive(read_mapping)

    monkeypatch.setattr("app.services.docx_formula_normalizer.ZipFile", fake_zipfile)
    monkeypatch.setattr("app.services.docx_formula_normalizer.os.makedirs", lambda *args, **kwargs: None)

    report = DocxFormulaNormalizer.flatten_axmath_to_images(input_path, output_path)

    assert report.normalized is True
    assert report.output_path == output_path
    assert report.flattened_axmath_count == 1
    assert "word/document.xml" in report.modified_parts

    document_xml = write_archive.written["word/document.xml"].decode("utf-8")
    rels_xml = write_archive.written["word/_rels/document.xml.rels"].decode("utf-8")
    names = set(write_archive.written)

    assert "Equation.AxMath" not in document_xml
    assert "<w:object" in document_xml
    assert 'o:ole="t"' not in document_xml
    assert 'r:id="rIdPreview"' in document_xml
    assert "rIdOle" not in rels_xml
    assert "word/embeddings/oleObject1.bin" not in names
    assert "word/media/image1.wmf" in names


def test_flatten_axmath_is_noop_for_plain_docx(monkeypatch):
    input_path = "D:/plain.docx"
    output_path = "D:/plain-out.docx"
    read_mapping = {
        "[Content_Types].xml": b"<Types></Types>",
        "word/document.xml": """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body>
</w:document>
""".encode("utf-8"),
    }
    write_calls = []

    def fake_zipfile(path, mode="r", compression=None):
        if mode == "w":
            write_calls.append(path)
            return FakeWriteZipArchive()
        assert path == input_path
        return FakeReadZipArchive(read_mapping)

    monkeypatch.setattr("app.services.docx_formula_normalizer.ZipFile", fake_zipfile)

    report = DocxFormulaNormalizer.flatten_axmath_to_images(input_path, output_path)

    assert report.normalized is False
    assert report.output_path == input_path
    assert report.flattened_axmath_count == 0
    assert write_calls == []
