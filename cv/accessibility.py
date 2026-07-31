"""Accessibility helpers: contrast arithmetic and text sanitisation.

These functions exist so that the WCAG 2.2 AAA guarantees of the generated
outputs are testable facts rather than aspirations: the test suite uses
them to verify that every colour the generator emits meets the 7:1
enhanced contrast ratio, and the builder uses them to construct plain-text
accessible names from marked-up titles.
"""

import re

# WCAG 2.x relative luminance constants
_SRGB_THRESHOLD = 0.03928
_AAA_RATIO = 7.0

_TAG_PATTERN = re.compile(r"<[^>]+>")


def _channel(value):
    """Linearise one sRGB channel (0-255) per the WCAG definition."""
    scaled = value / 255
    if scaled <= _SRGB_THRESHOLD:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour):
    """Return the WCAG relative luminance of a hex colour like '#6B5300'."""
    hex_colour = hex_colour.lstrip("#")
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))

    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(colour_a, colour_b):
    """Return the WCAG contrast ratio (1 to 21) between two hex colours."""
    lighter, darker = sorted(
        (relative_luminance(colour_a), relative_luminance(colour_b)), reverse=True
    )

    return (lighter + 0.05) / (darker + 0.05)


def meets_aaa(foreground, background="#FFFFFF"):
    """True if the pair meets the WCAG AAA enhanced contrast ratio of 7:1."""
    return contrast_ratio(foreground, background) >= _AAA_RATIO


def strip_markup(text):
    """Reduce an HTML-marked-up string to plain text for accessible names.

    Tags are removed and double quotes become apostrophes so that the
    result can sit safely inside a double-quoted HTML attribute.
    """
    return _TAG_PATTERN.sub("", text).replace('"', "'")
