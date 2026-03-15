import sys
from docx import Document
import xml.etree.ElementTree as ET

def check_docx(filepath):
    print(f"Checking {filepath}...")
    try:
        doc = Document(filepath)
    except Exception as e:
        print(f"Error reading docx: {e}")
        return

    paragraphs = list(doc.paragraphs)
    print(f"Number of paragraphs: {len(paragraphs)}")

    # Check for text in standard paragraphs
    text_content = [p.text for p in paragraphs if p.text.strip()]
    print(f"Number of standard non-empty paragraphs: {len(text_content)}")
    if text_content:
        print(f"Sample text from first non-empty paragraph: {text_content[0][:100]}")

    drawing_count = 0
    pict_count = 0
    shape_count = 0
    textbox_count = 0
    behind_doc_count = 0
    anchor_count = 0

    for p in paragraphs:
        p_xml = p._element.xml
        drawing_count += p_xml.count('<w:drawing>')
        pict_count += p_xml.count('<w:pict>')
        shape_count += p_xml.count('<v:shape')
        textbox_count += p_xml.count('<v:textbox') + p_xml.count('<w:txbxContent')
        anchor_count += p_xml.count('<wp:anchor')
        behind_doc_count += p_xml.count('behindDoc="1"')

    print(f"XML analysis:")
    print(f"  w:drawing count: {drawing_count}")
    print(f"  w:pict count: {pict_count}")
    print(f"  v:shape count: {shape_count}")
    print(f"  textbox count: {textbox_count}")
    print(f"  wp:anchor count: {anchor_count}")
    print(f"  behindDoc='1' count: {behind_doc_count}")

    is_high_risk = len(text_content) == 0 and (drawing_count > 0 or shape_count > 0 or textbox_count > 0)

    print(f"\nConclusion:")
    if is_high_risk:
        print("HIGH RISK: No regular text paragraphs found, but drawings/shapes/textboxes exist. This might be blank in Word.")
    else:
        print("Normal structure detected.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        check_docx(sys.argv[1])
    else:
        print("Usage: python check_docx.py <filepath>")
