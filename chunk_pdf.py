from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
import json
import re
import base64
import os
import argparse
from io import BytesIO

# Mapping of spec identifiers to human-readable names
SPEC_NAMES = {
    "80211be": "IEEE 802.11be (Wi-Fi 7)",
    "80211bn": "IEEE 802.11bn (Wi-Fi 8)",
    "80211ax": "IEEE 802.11ax (Wi-Fi 6)",
    "80211ac": "IEEE 802.11ac (Wi-Fi 5)",
}


def infer_section_level(title):
    """
    Infer section hierarchy level from the section number format.
    E.g., "9.4.2" -> level 3, "9.4.2.322.2.1" -> level 6
    """
    match = re.match(r'^(\d+(?:\.\d+)*)', title)
    if match:
        section_num = match.group(1)
        return section_num.count('.') + 1
    return 1


def is_in_page_range(page, start_page, end_page):
    """Check if a page number is within the specified range."""
    if page is None:
        return True  # Include items without page info
    if start_page is not None and page < start_page:
        return False
    if end_page is not None and page > end_page:
        return False
    return True


def extract_tables(doc, start_page=None, end_page=None):
    """
    Extract tables from document with their captions and content.
    Looks for 'Table' caption in section_header or caption above/below the table.

    Args:
        doc: The parsed document
        start_page: First page to include (1-indexed, inclusive)
        end_page: Last page to include (1-indexed, inclusive)
    """
    items = list(doc.iterate_items())
    tables = []

    for i, (item, level) in enumerate(items):
        label = getattr(item, "label", None)
        if label != "table":
            continue

        caption = None
        page = item.prov[0].page_no if hasattr(item, 'prov') and item.prov else None

        # Filter by page range
        if not is_in_page_range(page, start_page, end_page):
            continue

        # Look above for caption starting with "Table"
        if i > 0:
            prev_item, _ = items[i - 1]
            prev_label = getattr(prev_item, "label", None)
            prev_text = getattr(prev_item, "text", "").strip()
            if prev_label in ("section_header", "caption") and prev_text.startswith("Table"):
                caption = prev_text

        # If not found above, look below
        if not caption and i < len(items) - 1:
            next_item, _ = items[i + 1]
            next_label = getattr(next_item, "label", None)
            next_text = getattr(next_item, "text", "").strip()
            if next_label in ("section_header", "caption") and next_text.startswith("Table"):
                caption = next_text

        # Extract table content in markdown format
        content = None
        if hasattr(item, 'export_to_dataframe'):
            df = item.export_to_dataframe()
            content = df.to_markdown(index=False)

        tables.append({
            "caption": caption,
            "page": page,
            "content": content
        })

    return tables


def extract_figures(doc, output_dir="figures", spec=None, start_page=None, end_page=None):
    """
    Extract figures from document with their captions.
    Saves images to files and stores base64 in the output.

    Args:
        doc: The parsed document
        output_dir: Base directory for figures (will use output_dir/{spec}/ if spec provided)
        spec: Specification identifier for organizing output
        start_page: First page to include (1-indexed, inclusive)
        end_page: Last page to include (1-indexed, inclusive)
    """
    # If spec is provided, use figures/{spec}/ subdirectory
    if spec:
        output_dir = os.path.join(output_dir, spec)
    items = list(doc.iterate_items())
    figures = []

    # Create output directory for images
    os.makedirs(output_dir, exist_ok=True)

    for i, (item, level) in enumerate(items):
        label = getattr(item, "label", None)
        if label != "picture":
            continue

        caption = None
        page = item.prov[0].page_no if hasattr(item, 'prov') and item.prov else None

        # Filter by page range
        if not is_in_page_range(page, start_page, end_page):
            continue

        # Look above for caption starting with "Figure"
        if i > 0:
            prev_item, _ = items[i - 1]
            prev_label = getattr(prev_item, "label", None)
            prev_text = getattr(prev_item, "text", "").strip()
            if prev_label in ("section_header", "caption") and prev_text.startswith("Figure"):
                caption = prev_text

        # If not found above, look below
        if not caption and i < len(items) - 1:
            next_item, _ = items[i + 1]
            next_label = getattr(next_item, "label", None)
            next_text = getattr(next_item, "text", "").strip()
            if next_label in ("section_header", "caption") and next_text.startswith("Figure"):
                caption = next_text

        # Extract image
        image_base64 = None
        image_path = None
        if hasattr(item, 'get_image'):
            try:
                pil_image = item.get_image(doc)
                if pil_image:
                    # Generate filename from caption or index
                    if caption:
                        # Extract figure number (e.g., "9-1074o" from "Figure 9-1074o-...")
                        match = re.search(r'Figure\s+([\d\-\w]+)', caption)
                        filename = f"figure_{match.group(1)}.png" if match else f"figure_{i}.png"
                    else:
                        filename = f"figure_{i}.png"

                    image_path = os.path.join(output_dir, filename)

                    # Save to file
                    pil_image.save(image_path, "PNG")

                    # Convert to base64
                    buffer = BytesIO()
                    pil_image.save(buffer, format="PNG")
                    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            except Exception as e:
                print(f"Warning: Could not extract image at index {i}: {e}")

        figures.append({
            "caption": caption,
            "page": page,
            "image_path": image_path,
            "image_base64": image_base64
        })

    return figures


def extract_sections(pdf_path, output_path, spec=None, start_page=None, end_page=None):
    """
    Extract sections from a PDF file and save to JSON.

    Args:
        pdf_path: Path to the PDF file
        output_path: Path for the output JSON file
        spec: Specification identifier (e.g., "80211be", "80211bn")
        start_page: First page to include (1-indexed, inclusive)
        end_page: Last page to include (1-indexed, inclusive)

    Returns:
        List of extracted sections
    """
    # Configure pipeline to extract images
    pipeline_options = PdfPipelineOptions()
    pipeline_options.images_scale = 2.0
    pipeline_options.generate_picture_images = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    result = converter.convert(pdf_path)
    doc = result.document

    sections = []
    current_section = None
    current_text = []

    for item, level in doc.iterate_items():
        label = getattr(item, "label", None)
        text = getattr(item, "text", "").strip()
        page = item.prov[0].page_no if hasattr(item, 'prov') and item.prov else None

        # Filter by page range
        if not is_in_page_range(page, start_page, end_page):
            continue

        # Section header must start with a number (e.g., "9.4.2.322.2")
        is_valid_section = (label == "section_header" and
                           text and
                           re.match(r'^\d+', text))

        if is_valid_section:
            # Save previous section
            if current_section:
                current_section["text"] = "\n".join(current_text)
                sections.append(current_section)

            # Start new section
            current_section = {
                "section_title": text,
                "level": infer_section_level(text),
                "page": page
            }
            current_text = []

        elif label in ("text", "paragraph", "list_item") and text and current_section:
            current_text.append(text)

    # Don't forget last section
    if current_section:
        current_section["text"] = "\n".join(current_text)
        sections.append(current_section)

    # Extract tables and figures
    tables = extract_tables(doc, start_page, end_page)
    figures = extract_figures(doc, spec=spec, start_page=start_page, end_page=end_page)

    # Build output with spec metadata if provided
    output = {"sections": sections, "tables": tables, "figures": figures}
    if spec:
        output["spec"] = spec
        output["spec_name"] = SPEC_NAMES.get(spec, f"IEEE 802.11 ({spec})")

    # Add page range info if specified
    if start_page or end_page:
        output["page_range"] = {
            "start": start_page,
            "end": end_page
        }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    page_info = ""
    if start_page or end_page:
        page_info = f" (pages {start_page or 1}-{end_page or 'end'})"
    print(f"Extracted {len(sections)} sections, {len(tables)} tables, {len(figures)} figures{page_info} to {output_path}")
    if spec:
        print(f"Spec: {output['spec_name']}")
    return sections, tables, figures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract sections, tables, and figures from IEEE 802.11 PDFs"
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument(
        "--spec",
        help="Specification identifier (e.g., '80211be', '80211bn')"
    )
    parser.add_argument(
        "--output",
        help="Output JSON filename (default: {spec}_output.json or sections_output.json)"
    )
    parser.add_argument(
        "--start-page",
        type=int,
        help="First page to extract (1-indexed, inclusive)"
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="Last page to extract (1-indexed, inclusive)"
    )

    args = parser.parse_args()

    # Determine output filename
    if args.output:
        output_path = args.output
    elif args.spec:
        output_path = f"{args.spec}_output.json"
    else:
        output_path = "sections_output.json"

    extract_sections(
        args.pdf,
        output_path,
        spec=args.spec,
        start_page=args.start_page,
        end_page=args.end_page
    )
