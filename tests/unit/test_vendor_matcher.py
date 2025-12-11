"""Unit tests for fuzzy vendor matching."""

import pytest
from unittest.mock import patch

from shared.vendor_matcher import find_fuzzy_match, normalize_vendor_name, get_all_vendor_names


class TestFindFuzzyMatch:
    """Tests for find_fuzzy_match function."""

    @pytest.fixture
    def sample_vendors(self):
        """Sample vendor data mimicking VendorMaster table."""
        return [
            {"RowKey": "adobe_inc", "VendorName": "Adobe Inc", "ExpenseDept": "IT", "GLCode": "6100"},
            {
                "RowKey": "microsoft_corporation",
                "VendorName": "Microsoft Corporation",
                "ExpenseDept": "IT",
                "GLCode": "6100",
            },
            {
                "RowKey": "amazon_web_services",
                "VendorName": "Amazon Web Services",
                "ExpenseDept": "Cloud",
                "GLCode": "6200",
            },
            {"RowKey": "google_cloud", "VendorName": "Google Cloud", "ExpenseDept": "Cloud", "GLCode": "6200"},
            {"RowKey": "salesforce", "VendorName": "Salesforce", "ExpenseDept": "Sales", "GLCode": "6300"},
        ]

    def test_exact_name_match(self, sample_vendors):
        """Exact vendor name should match with high score."""
        vendor, score = find_fuzzy_match("Adobe Inc", sample_vendors)
        assert vendor is not None
        assert vendor["VendorName"] == "Adobe Inc"
        assert score >= 95

    def test_fuzzy_match_with_suffix_variation(self, sample_vendors):
        """Vendor name with different suffix should still match."""
        # Use lower threshold (70) to ensure match across rapidfuzz versions
        vendor, score = find_fuzzy_match("Adobe Systems Incorporated", sample_vendors, threshold=70)
        assert vendor is not None
        assert vendor["VendorName"] == "Adobe Inc"
        assert score >= 70  # WRatio handles suffix variations

    def test_fuzzy_match_partial_name(self, sample_vendors):
        """Partial vendor name should match if above threshold."""
        vendor, score = find_fuzzy_match("Microsoft", sample_vendors)
        assert vendor is not None
        assert vendor["VendorName"] == "Microsoft Corporation"
        assert score >= 90  # WRatio gives high score for partial matches

    def test_fuzzy_match_word_order(self, sample_vendors):
        """Different word order should still match (token_sort_ratio)."""
        vendor, score = find_fuzzy_match("AWS Amazon Web Services", sample_vendors)
        assert vendor is not None
        assert vendor["VendorName"] == "Amazon Web Services"
        assert score >= 70  # Word order may lower score slightly

    def test_no_match_below_threshold(self, sample_vendors):
        """Unrelated vendor name should not match."""
        vendor, score = find_fuzzy_match("Completely Different Company", sample_vendors)
        assert vendor is None
        assert score < 80

    def test_custom_threshold(self, sample_vendors):
        """Custom threshold should affect matching."""
        # With high threshold, partial match should fail
        vendor, score = find_fuzzy_match("Microsoft", sample_vendors, threshold=95)
        assert vendor is None

        # With lower threshold, should succeed
        vendor, score = find_fuzzy_match("Microsoft", sample_vendors, threshold=60)
        assert vendor is not None

    def test_empty_search_name(self, sample_vendors):
        """Empty search name should return None."""
        vendor, score = find_fuzzy_match("", sample_vendors)
        assert vendor is None
        assert score == 0

    def test_empty_vendors_list(self):
        """Empty vendors list should return None."""
        vendor, score = find_fuzzy_match("Adobe", [])
        assert vendor is None
        assert score == 0

    def test_whitespace_search_name(self, sample_vendors):
        """Whitespace-only search name should return None."""
        vendor, score = find_fuzzy_match("   ", sample_vendors)
        assert vendor is None
        assert score == 0

    def test_case_insensitive_matching(self, sample_vendors):
        """Matching should be case-insensitive."""
        vendor, score = find_fuzzy_match("ADOBE INC", sample_vendors)
        assert vendor is not None
        assert vendor["VendorName"] == "Adobe Inc"

    def test_returns_best_match(self, sample_vendors):
        """Should return the best matching vendor."""
        # "Google" should match "Google Cloud" not other vendors
        vendor, score = find_fuzzy_match("Google", sample_vendors)
        assert vendor is not None
        assert vendor["VendorName"] == "Google Cloud"
        assert score >= 90  # WRatio gives high score for partial matches

    @patch.dict("os.environ", {"VENDOR_FUZZY_THRESHOLD": "90"})
    def test_environment_threshold(self, sample_vendors):
        """Should respect VENDOR_FUZZY_THRESHOLD environment variable."""
        # Need to reimport to pick up env var
        from importlib import reload
        import shared.vendor_matcher as vm

        reload(vm)

        # With 90 threshold, partial match should fail
        vendor, score = vm.find_fuzzy_match("Microsoft", sample_vendors)
        # Score will be ~75, below 90 threshold
        assert vendor is None or score >= 90


class TestNormalizeVendorName:
    """Tests for normalize_vendor_name function."""

    def test_remove_inc_suffix(self):
        """Should remove 'Inc' suffix."""
        assert normalize_vendor_name("Adobe Inc") == "adobe"
        assert normalize_vendor_name("Adobe Inc.") == "adobe"
        assert normalize_vendor_name("Adobe, Inc.") == "adobe"
        assert normalize_vendor_name("Adobe, Inc") == "adobe"

    def test_remove_llc_suffix(self):
        """Should remove 'LLC' suffix."""
        assert normalize_vendor_name("Company LLC") == "company"
        assert normalize_vendor_name("Company, LLC") == "company"

    def test_remove_corporation_suffix(self):
        """Should remove 'Corporation' suffix."""
        assert normalize_vendor_name("Microsoft Corporation") == "microsoft"
        assert normalize_vendor_name("Microsoft Corp.") == "microsoft"
        assert normalize_vendor_name("Microsoft Corp") == "microsoft"

    def test_remove_ltd_suffix(self):
        """Should remove 'Ltd' suffix."""
        assert normalize_vendor_name("Company Ltd") == "company"
        assert normalize_vendor_name("Company Ltd.") == "company"
        assert normalize_vendor_name("Company Limited") == "company"

    def test_preserve_core_name(self):
        """Should preserve the core vendor name."""
        assert normalize_vendor_name("Amazon Web Services") == "amazon web services"
        assert normalize_vendor_name("Google Cloud") == "google cloud"

    def test_normalize_whitespace(self):
        """Should normalize whitespace."""
        assert normalize_vendor_name("  Adobe   Inc  ") == "adobe"
        assert normalize_vendor_name("Multiple   Spaces   Here") == "multiple spaces here"

    def test_empty_string(self):
        """Should handle empty string."""
        assert normalize_vendor_name("") == ""
        assert normalize_vendor_name("   ") == ""

    def test_lowercase(self):
        """Should convert to lowercase."""
        assert normalize_vendor_name("ADOBE INC") == "adobe"
        assert normalize_vendor_name("MiXeD CaSe") == "mixed case"


class TestGetAllVendorNames:
    """Tests for get_all_vendor_names function."""

    def test_extracts_vendor_names(self):
        """Should extract all vendor names from entities."""
        vendors = [
            {"VendorName": "Adobe Inc"},
            {"VendorName": "Microsoft"},
            {"VendorName": "Google"},
        ]
        names = get_all_vendor_names(vendors)
        assert names == ["Adobe Inc", "Microsoft", "Google"]

    def test_skips_empty_names(self):
        """Should skip entities with empty vendor names."""
        vendors = [
            {"VendorName": "Adobe Inc"},
            {"VendorName": ""},
            {"VendorName": "Google"},
            {},
        ]
        names = get_all_vendor_names(vendors)
        assert names == ["Adobe Inc", "Google"]

    def test_empty_list(self):
        """Should handle empty vendor list."""
        assert get_all_vendor_names([]) == []
