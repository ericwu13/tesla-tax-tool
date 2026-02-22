"""PDF text extraction engine with OCR fallback and form type auto-detection."""

import os
import re

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

from form_parsers import get_parser


# Minimum characters of extracted text before falling back to OCR
_MIN_TEXT_LENGTH = 50

# Keywords for form type detection.
# Patterns avoid \b before digits — pdfplumber often merges words
# (e.g., "Form1099-INT" has no word boundary between "m" and "1").
# Use \s* instead of \s+ to handle merged words (e.g., "Interestincome").
_FORM_SIGNATURES = [
    ('W-2', [
        r'wage\s*and\s*tax\s*statement',
        r'w[\-\s]?2\b',
        r'employer.?s?\s*(?:name|identification)',
    ]),
    ('1099-B', [
        r'proceeds\s*from\s*broker',
        r'1099[\-\s]?B\b',
        r'barter\s*exchange\s*transactions',
    ]),
    ('1099-INT', [
        r'1099[\-\s]?INT',
        r'interest\s*income',
    ]),
    ('1098', [
        r'mortgage\s*interest\s*statement',
        r'1098\b',
        r'mortgage\s*interest\s*received',
    ]),
]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file. Falls back to OCR if text is empty/minimal."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = ''

    # Primary: pdfplumber (handles digital/text-based PDFs)
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                text = '\n'.join(pages_text)
        except Exception as e:
            print(f"  pdfplumber error: {e}")

    # Fallback: OCR for scanned/image PDFs
    if len(text.strip()) < _MIN_TEXT_LENGTH:
        if HAS_OCR:
            try:
                print("  Text extraction minimal, attempting OCR...")
                images = convert_from_path(pdf_path)
                ocr_pages = []
                for img in images:
                    ocr_pages.append(pytesseract.image_to_string(img))
                text = '\n'.join(ocr_pages)
            except Exception as e:
                print(f"  OCR error: {e}")
        elif not HAS_PDFPLUMBER:
            raise ImportError(
                "No PDF extraction library available. Install pdfplumber:\n"
                "  pip install pdfplumber\n"
                "For scanned PDFs, also install:\n"
                "  pip install pytesseract pdf2image Pillow"
            )
        elif len(text.strip()) < _MIN_TEXT_LENGTH:
            print(
                "  Warning: Very little text extracted. This may be a scanned PDF.\n"
                "  For OCR support, install: pip install pytesseract pdf2image Pillow"
            )

    return text


def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image file using OCR."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not HAS_OCR:
        raise ImportError(
            "OCR not available. Install:\n"
            "  pip install pytesseract Pillow\n"
            "Also install Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
        )

    from PIL import Image
    img = Image.open(image_path)
    return pytesseract.image_to_string(img)


def detect_form_type(text: str) -> str:
    """
    Auto-detect the primary tax form type from extracted text content.

    Returns: 'W-2', '1099-B', '1099-INT', '1098', or 'unknown'
    """
    for form_type, patterns in _FORM_SIGNATURES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return form_type
    return 'unknown'


def detect_all_form_types(text: str) -> list:
    """
    Detect ALL tax form types present in the text.

    Brokerages often issue consolidated 1099 PDFs containing 1099-B, 1099-INT,
    and 1099-DIV in a single document. This function returns all detected types
    so each relevant parser can run.

    Returns: list of form type strings, e.g. ['1099-B', '1099-INT']
    """
    detected = []
    for form_type, patterns in _FORM_SIGNATURES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(form_type)
                break
    return detected if detected else ['unknown']


def _extract_text(file_path: str) -> str:
    """Extract text from a PDF or image file."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'):
        return extract_text_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use PDF or image files.")


def scan_form(file_path: str, tax_year: int = None) -> dict:
    """
    Scan a single file and return the primary detected form type.

    For backwards compatibility, returns a single result dict.
    Use scan_form_multi() for consolidated documents.

    Returns:
        {
            'form_type': str,
            'data': dict|list,
            'source_file': str,
            'raw_text': str,
        }
    """
    text = _extract_text(file_path)
    form_type = detect_form_type(text)
    print(f"  Detected form type: {form_type}")

    data = {}
    parser = get_parser(form_type)
    if parser:
        kwargs = {'tax_year': tax_year} if tax_year else {}
        data = parser(text, **kwargs)
    else:
        print(f"  Warning: No parser available for form type '{form_type}'")

    return {
        'form_type': form_type,
        'data': data,
        'source_file': file_path,
        'raw_text': text,
    }


def scan_form_multi(file_path: str, tax_year: int = None) -> list:
    """
    Scan a single file and return results for ALL detected form types.

    Handles consolidated 1099 PDFs that contain multiple form types
    (e.g., 1099-B + 1099-INT + 1099-DIV in one document).

    Returns:
        List of result dicts, one per detected form type. Each has:
        {
            'form_type': str,
            'data': dict|list,
            'source_file': str,
            'raw_text': str,
        }
    """
    text = _extract_text(file_path)
    form_types = detect_all_form_types(text)
    print(f"  Detected form type(s): {', '.join(form_types)}")

    results = []
    kwargs = {'tax_year': tax_year} if tax_year else {}

    for form_type in form_types:
        parser = get_parser(form_type)
        if parser:
            data = parser(text, **kwargs)
            # Only include if the parser found meaningful data
            if _has_data(form_type, data):
                results.append({
                    'form_type': form_type,
                    'data': data,
                    'source_file': file_path,
                    'raw_text': text,
                })
            else:
                print(f"  {form_type}: detected but no data extracted, skipping")
        else:
            print(f"  Warning: No parser available for form type '{form_type}'")

    # If no parsers produced data, return a single unknown result
    if not results:
        results.append({
            'form_type': form_types[0] if form_types else 'unknown',
            'data': {},
            'source_file': file_path,
            'raw_text': text,
        })

    return results


def _has_data(form_type: str, data) -> bool:
    """Check if a parser returned meaningful data (not all zeros/empty)."""
    if not data:
        return False
    if isinstance(data, list):
        return len(data) > 0
    if form_type == '1099-INT':
        return data.get('total_interest', 0) > 0
    if form_type == '1099-B':
        return isinstance(data, list) and len(data) > 0
    if form_type == '1098':
        return (data.get('mortgage_interest', 0) > 0
                or data.get('property_taxes', 0) > 0)
    if form_type == 'W-2':
        return data.get('wages', 0) > 0
    return True
