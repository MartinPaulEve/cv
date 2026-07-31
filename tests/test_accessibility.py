"""Tests for the WCAG arithmetic and the accessibility of generated markup.

These tests turn the WCAG 2.2 AAA requirements into executable checks:
the contrast mathematics follow the WCAG definition, and the colours that
the generator is configured to emit must meet the 7:1 enhanced contrast
ratio against a white page. If someone later edits a colour in the
configuration, these tests fail rather than letting the output quietly
regress below AAA.
"""

import pytest

from cv.accessibility import (
    contrast_ratio,
    meets_aaa,
    relative_luminance,
    strip_markup,
)


class TestContrastArithmetic:
    def test_black_luminance_is_zero(self):
        assert relative_luminance("#000000") == 0

    def test_white_luminance_is_one(self):
        assert relative_luminance("#FFFFFF") == pytest.approx(1.0)

    def test_black_on_white_is_maximum_contrast(self):
        assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)

    def test_contrast_is_symmetric(self):
        assert contrast_ratio("#175117", "#FFFFFF") == pytest.approx(
            contrast_ratio("#FFFFFF", "#175117")
        )

    def test_same_colour_has_no_contrast(self):
        assert contrast_ratio("#34539C", "#34539C") == pytest.approx(1.0)

    def test_hash_prefix_is_optional(self):
        assert contrast_ratio("000000", "ffffff") == pytest.approx(21.0)


class TestAaaJudgements:
    def test_goldenrod_fails_aaa(self):
        # the colour this project used to emit: roughly 2.2:1
        assert meets_aaa("#DAA520") is False

    def test_css_green_fails_aaa(self):
        assert meets_aaa("#008000") is False

    def test_dark_gold_replacement_passes_aaa(self):
        assert meets_aaa("#6B5300") is True

    def test_dark_green_replacement_passes_aaa(self):
        assert meets_aaa("#175117") is True

    def test_body_link_colour_passes_aaa(self):
        # the link colour used in the PDF stylesheet
        assert meets_aaa("#34539C") is True


class TestStripMarkup:
    def test_tags_are_removed(self):
        assert strip_markup("On <i>Gravity's Rainbow</i> and history") == (
            "On Gravity's Rainbow and history"
        )

    def test_nested_tags_are_removed(self):
        assert strip_markup("<i>A <span>B</span></i> C") == "A B C"

    def test_quotes_are_neutralised_for_attribute_use(self):
        assert '"' not in strip_markup('A "quoted" title')

    def test_plain_text_is_unchanged(self):
        assert strip_markup("Plain title") == "Plain title"


class TestConfiguredColoursMeetAaa:
    def test_all_configured_oa_colours_meet_aaa(self, fake_config):
        for route, colour in fake_config.oa_colors.items():
            assert meets_aaa(colour), (
                f"open access colour for {route} route fails AAA contrast"
            )
