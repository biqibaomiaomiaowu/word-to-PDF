from __future__ import annotations

import copy
import os
import posixpath
from dataclasses import dataclass, field
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET


WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
VML_NS = "urn:schemas-microsoft-com:vml"
OFFICE_NS = "urn:schemas-microsoft-com:office:office"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("w", WORDPROCESSING_NS)
ET.register_namespace("r", RELATIONSHIP_NS)
ET.register_namespace("m", MATH_NS)
ET.register_namespace("v", VML_NS)
ET.register_namespace("o", OFFICE_NS)

W_OBJECT_TAG = f"{{{WORDPROCESSING_NS}}}object"
O_OLEOBJECT_TAG = f"{{{OFFICE_NS}}}OLEObject"
V_IMAGEDATA_TAG = f"{{{VML_NS}}}imagedata"
RELATIONSHIP_TAG = f"{{{PACKAGE_REL_NS}}}Relationship"
OLE_FLAG_ATTR = f"{{{OFFICE_NS}}}ole"
REL_ID_ATTR = f"{{{RELATIONSHIP_NS}}}id"
AXMATH_PROG_ID = "Equation.AxMath"


@dataclass(slots=True)
class DocxFormulaNormalizationReport:
    output_path: str
    normalized: bool
    flattened_axmath_count: int = 0
    modified_parts: list[str] = field(default_factory=list)
    dropped_embed_parts: list[str] = field(default_factory=list)


def _iter_word_xml_parts(archive: ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name.startswith("word/")
        and name.endswith(".xml")
        and "/_rels/" not in name
    ]


def _scrub_ole_markup(node: ET.Element) -> None:
    for element in node.iter():
        if OLE_FLAG_ATTR in element.attrib:
            del element.attrib[OLE_FLAG_ATTR]


def _flatten_axmath_object(object_element: ET.Element) -> tuple[ET.Element | None, list[str]]:
    ole_children = [child for child in list(object_element) if child.tag == O_OLEOBJECT_TAG]
    if not ole_children:
        return None, []

    if any(child.get("ProgID") != AXMATH_PROG_ID for child in ole_children):
        return None, []

    preview_children: list[ET.Element] = []
    removed_rel_ids: list[str] = []

    for child in list(object_element):
        if child.tag == O_OLEOBJECT_TAG:
            rel_id = child.get(REL_ID_ATTR)
            if rel_id:
                removed_rel_ids.append(rel_id)
            continue

        cloned_child = copy.deepcopy(child)
        _scrub_ole_markup(cloned_child)
        preview_children.append(cloned_child)

    if not preview_children:
        return None, []

    flattened_object = ET.Element(W_OBJECT_TAG)
    for child in preview_children:
        flattened_object.append(child)

    if not any(element.tag == V_IMAGEDATA_TAG for element in flattened_object.iter()):
        return None, []

    return flattened_object, removed_rel_ids


def _flatten_axmath_in_xml(xml_bytes: bytes) -> tuple[bytes | None, int, list[str]]:
    root = ET.fromstring(xml_bytes)
    flattened_count = 0
    removed_rel_ids: list[str] = []

    for parent in root.iter():
        replacements: list[tuple[int, ET.Element, ET.Element]] = []
        for index, child in enumerate(list(parent)):
            if child.tag != W_OBJECT_TAG:
                continue

            pict_element, rel_ids = _flatten_axmath_object(child)
            if pict_element is None:
                continue

            replacements.append((index, child, pict_element))
            removed_rel_ids.extend(rel_ids)
            flattened_count += 1

        for index, original, replacement in reversed(replacements):
            parent.remove(original)
            parent.insert(index, replacement)

    if flattened_count == 0:
        return None, 0, []

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), flattened_count, removed_rel_ids


def _relationships_path_for_part(part_name: str) -> str:
    part_dir = posixpath.dirname(part_name)
    part_file = posixpath.basename(part_name)
    return posixpath.join(part_dir, "_rels", f"{part_file}.rels")


def _resolve_relationship_target(part_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(part_name), target))


def _remove_relationship_targets(
    rels_bytes: bytes,
    source_part: str,
    removed_rel_ids: list[str],
) -> tuple[bytes | None, list[str]]:
    root = ET.fromstring(rels_bytes)
    dropped_targets: list[str] = []
    modified = False

    for relationship in list(root):
        if relationship.tag != RELATIONSHIP_TAG:
            continue
        if relationship.get("Id") not in removed_rel_ids:
            continue

        target = relationship.get("Target")
        if target:
            dropped_targets.append(_resolve_relationship_target(source_part, target))
        root.remove(relationship)
        modified = True

    if not modified:
        return None, []

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), dropped_targets


class DocxFormulaNormalizer:
    @staticmethod
    def flatten_axmath_to_images(
        input_path: str,
        output_path: str,
    ) -> DocxFormulaNormalizationReport:
        if os.path.splitext(input_path)[1].lower() != ".docx":
            return DocxFormulaNormalizationReport(
                output_path=input_path,
                normalized=False,
            )

        if os.path.abspath(input_path) == os.path.abspath(output_path):
            raise ValueError("AxMath normalization requires a separate output path.")

        try:
            with ZipFile(input_path) as archive:
                archive_names = set(archive.namelist())
                replacements: dict[str, bytes] = {}
                dropped_embed_parts: set[str] = set()
                modified_parts: list[str] = []
                flattened_total = 0

                for part_name in _iter_word_xml_parts(archive):
                    xml_bytes = archive.read(part_name)
                    updated_xml, flattened_count, removed_rel_ids = _flatten_axmath_in_xml(xml_bytes)
                    if flattened_count == 0 or updated_xml is None:
                        continue

                    replacements[part_name] = updated_xml
                    modified_parts.append(part_name)
                    flattened_total += flattened_count

                    if not removed_rel_ids:
                        continue

                    rels_name = _relationships_path_for_part(part_name)
                    if rels_name not in archive_names:
                        continue

                    updated_rels, removed_targets = _remove_relationship_targets(
                        archive.read(rels_name),
                        part_name,
                        removed_rel_ids,
                    )
                    if updated_rels is not None:
                        replacements[rels_name] = updated_rels
                    dropped_embed_parts.update(
                        target for target in removed_targets if target.startswith("word/embeddings/")
                    )

                if flattened_total == 0:
                    return DocxFormulaNormalizationReport(
                        output_path=input_path,
                        normalized=False,
                    )

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as output_archive:
                    for info in archive.infolist():
                        if info.filename in dropped_embed_parts:
                            continue
                        payload = replacements.get(info.filename)
                        if payload is None:
                            payload = archive.read(info.filename)
                        output_archive.writestr(info, payload)
        except (OSError, BadZipFile, ET.ParseError) as exc:
            raise ValueError(f"Failed to normalize AxMath objects in {input_path}: {exc}") from exc

        return DocxFormulaNormalizationReport(
            output_path=output_path,
            normalized=True,
            flattened_axmath_count=flattened_total,
            modified_parts=modified_parts,
            dropped_embed_parts=sorted(dropped_embed_parts),
        )
