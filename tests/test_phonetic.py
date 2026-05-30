"""Tests for the phonetic name-matching module."""

from census_search.phonetic import name_similarity, soundex


class TestSoundex:
    def test_exact_same_name(self):
        assert soundex("Corrigan") == soundex("Corrigan")

    def test_variant_spelling_same_code(self):
        """Common Irish surname spelling variants should map to the same code."""
        assert soundex("Corrigan") == soundex("Corigan")
        assert soundex("Purcell") == soundex("Pursell")
        assert soundex("Murphy") == soundex("Murphey")
        assert soundex("Brien") == soundex("Bryan")

    def test_different_surnames_different_codes(self):
        assert soundex("Corrigan") != soundex("Murphy")
        assert soundex("Kelly") != soundex("Corrigan")

    def test_empty_string(self):
        assert soundex("") == "0000"

    def test_single_char(self):
        code = soundex("M")
        assert code[0] == "M"
        assert len(code) == 4

    def test_code_length_always_four(self):
        for name in ["A", "Murphy", "O'Brien", "MacCarthy", "Ni"]:
            assert len(soundex(name)) == 4

    def test_first_letter_preserved(self):
        assert soundex("Kelly")[0] == "K"
        assert soundex("Murphy")[0] == "M"
        assert soundex("Walsh")[0] == "W"

    def test_ignores_non_alpha(self):
        # Apostrophes and hyphens should be stripped
        assert soundex("O'Brien") == soundex("OBrien")

    def test_h_w_ignored(self):
        # H and W don't affect the code
        assert soundex("Ahearn") == soundex("Aearn")


class TestNameSimilarity:
    def test_identical(self):
        assert name_similarity("Mary", "Mary") == 1.0

    def test_empty_returns_zero(self):
        assert name_similarity("", "Mary") == 0.0
        assert name_similarity("Mary", "") == 0.0

    def test_case_insensitive(self):
        assert name_similarity("mary", "Mary") == name_similarity("Mary", "Mary")

    def test_similar_names_high_score(self):
        # "Mary" vs "Marie" — close enough (difflib gives ~0.67)
        assert name_similarity("Mary", "Marie") > 0.60

    def test_very_different_names_low_score(self):
        assert name_similarity("Mary", "Patrick") < 0.40

    def test_prefix_high_score(self):
        # "Pat" is a prefix of "Patrick"
        assert name_similarity("Pat", "Patrick") >= 0.60
