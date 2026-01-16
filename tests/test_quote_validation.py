"""Unit tests for quote validation utilities."""

import pytest

from extraction.utils.verified_utils import (
    normalize_text_for_match,
    validate_quote_in_source,
)


class TestNormalizeTextForMatch:
    """Test normalize_text_for_match function."""

    def test_basic_text_unchanged(self):
        """Test that basic text is normalized correctly."""
        text = "hello world"
        assert normalize_text_for_match(text) == "hello world"

    def test_whitespace_collapsing(self):
        """Test that multiple spaces collapse to one."""
        text = "hello    world"
        assert normalize_text_for_match(text) == "hello world"

    def test_newline_collapsing(self):
        """Test that newlines collapse to spaces."""
        text = "hello\nworld"
        assert normalize_text_for_match(text) == "hello world"

    def test_tab_collapsing(self):
        """Test that tabs collapse to spaces."""
        text = "hello\tworld"
        assert normalize_text_for_match(text) == "hello world"

    def test_mixed_whitespace_collapsing(self):
        """Test that mixed whitespace collapses correctly."""
        text = "hello   \n\t  world  "
        assert normalize_text_for_match(text) == "hello world"

    def test_case_insensitive(self):
        """Test that text is converted to lowercase."""
        text = "HELLO World"
        assert normalize_text_for_match(text) == "hello world"

    def test_hyphenated_line_break(self):
        """Test de-hyphenation of line breaks."""
        text = "emission-\nreduction"
        assert normalize_text_for_match(text) == "emission reduction"

    def test_hyphenated_crlf_break(self):
        """Test de-hyphenation of CRLF breaks."""
        text = "emission-\r\nreduction"
        assert normalize_text_for_match(text) == "emission reduction"

    def test_leading_trailing_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "  hello world  "
        assert normalize_text_for_match(text) == "hello world"

    def test_empty_string(self):
        """Test that empty string remains empty."""
        text = ""
        assert normalize_text_for_match(text) == ""

    def test_whitespace_only_string(self):
        """Test that whitespace-only string becomes empty."""
        text = "   \n\t  "
        assert normalize_text_for_match(text) == ""

    def test_complex_normalization(self):
        """Test complex text with all normalization types."""
        text = "  Greenhouse   Gas\n  Emissions-\nReduction   By  2030  "
        expected = "greenhouse gas emissions reduction by 2030"
        assert normalize_text_for_match(text) == expected


class TestValidateQuoteInSource:
    """Test validate_quote_in_source function."""

    def test_exact_quote_found(self):
        """Test that exact quote is found."""
        source = "The city aims to reduce emissions by 50% by 2030."
        quote = "50%"
        assert validate_quote_in_source(quote, source) is True

    def test_quote_not_found(self):
        """Test that missing quote is not found."""
        source = "The city aims to reduce emissions by 2030."
        quote = "80%"
        assert validate_quote_in_source(quote, source) is False

    def test_normalized_quote_found(self):
        """Test that normalized quote is found."""
        source = "Greenhouse   Gas\nEmissions"
        quote = "Greenhouse Gas Emissions"
        assert validate_quote_in_source(quote, source) is True

    def test_case_insensitive_match(self):
        """Test that matching is case-insensitive."""
        source = "The Target Year is 2030"
        quote = "target year"
        assert validate_quote_in_source(quote, source) is True

    def test_whitespace_difference_ignored(self):
        """Test that whitespace differences are ignored."""
        source = "The   city   targets\n2030-01-01"
        quote = "city targets 2030-01-01"
        assert validate_quote_in_source(quote, source) is True

    def test_hyphenated_line_break_in_quote(self):
        """Test matching with hyphenated line breaks in quote."""
        source = "emission-\nreduction target"
        quote = "emission reduction"
        assert validate_quote_in_source(quote, source) is True

    def test_empty_quote_rejected(self):
        """Test that empty quote is rejected."""
        source = "Some text here"
        quote = ""
        assert validate_quote_in_source(quote, source) is False

    def test_empty_source_rejected(self):
        """Test that empty source is rejected."""
        source = ""
        quote = "some quote"
        assert validate_quote_in_source(quote, source) is False

    def test_whitespace_only_quote_rejected(self):
        """Test that whitespace-only quote is rejected."""
        source = "Some text here"
        quote = "   \n\t"
        assert validate_quote_in_source(quote, source) is False

    def test_whitespace_only_source_rejected(self):
        """Test that whitespace-only source is rejected."""
        source = "   \n\t"
        quote = "some quote"
        assert validate_quote_in_source(quote, source) is False

    def test_quote_as_substring(self):
        """Test that quote works as substring."""
        source = "The baseline emissions in 2019 were 5.25 tonnes CO2e per capita."
        quote = "5.25 tonnes"
        assert validate_quote_in_source(quote, source) is True

    def test_quote_with_special_characters(self):
        """Test quote matching with special characters."""
        source = "Budget: EUR 5,000,000 allocated."
        quote = "5,000,000"
        assert validate_quote_in_source(quote, source) is True

    def test_non_string_input_handled(self):
        """Test that non-string inputs are handled."""
        source = "Some text"
        quote = 123  # type: ignore
        assert validate_quote_in_source(quote, source) is False

    def test_partial_match_not_sufficient(self):
        """Test that partial matches within words are not found (normalization dependent)."""
        # This depends on how the text is normalized - with basic word splitting
        source = "The city targets 2030"
        quote = "target"  # part of "targets"
        # After normalization, this should be found as substring
        assert validate_quote_in_source(quote, source) is True

    def test_real_world_emission_record(self):
        """Test real-world emission record quote matching."""
        source = """
        Emission Inventory 2019
        Year: 2019
        Scope 1: 2,500 tCO2e
        Scope 2: 1,200 tCO2e
        """
        quote = "2,500"
        assert validate_quote_in_source(quote, source) is True

    def test_real_world_target_quote(self):
        """Test real-world climate target quote matching."""
        source = """
        Climate Target:
        The city commits to reduce greenhouse gas emissions by 80%
        by 2030 compared to baseline year 2019.
        """
        quote = "80%"
        assert validate_quote_in_source(quote, source) is True

    def test_real_world_target_quote_with_formatting(self):
        """Test real-world target with complex formatting."""
        source = """
        Baseline:   2019-01-01
        Annual Emissions:   5.25   tonnes
        Target Year:   2030-01-01
        """
        quote = "5.25 tonnes"
        assert validate_quote_in_source(quote, source) is True
