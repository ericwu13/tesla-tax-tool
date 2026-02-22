"""Form parser registry for tax document extraction."""

from form_parsers.w2_parser import parse_w2
from form_parsers.f1099b_parser import parse_1099b
from form_parsers.f1099int_parser import parse_1099int
from form_parsers.f1098_parser import parse_1098

PARSERS = {
    'W-2': parse_w2,
    '1099-B': parse_1099b,
    '1099-INT': parse_1099int,
    '1098': parse_1098,
}


def get_parser(form_type: str):
    """Return the parser function for a given form type, or None."""
    return PARSERS.get(form_type)
