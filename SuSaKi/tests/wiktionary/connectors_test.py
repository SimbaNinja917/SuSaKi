'''
Created on May 12, 2016

@author: simon
'''
import pytest


class HTMLConnectorTest:

    def test_returns_error_when_word_is_completely_unknown(self):
        assert False

    def test_returns_suggestions_when_the_word_doesnt_have_an_article_but_exists_in_other_article(self):
        assert False

    def test_returns_article_when_word_has_an_article(self):
        assert False

# Following tests should be in other class since they are about the
# parsing of the page and not retrieval

    def test_only_returns_article_in_correct_target_language(self):
        assert False

    def test_can_translate_from_english_to_target_language(self):
        assert False

    def test_returns_synonyms_if_they_exists(self):
        assert False

    def test_returns_derived_terms_if_they_exists(self):
        assert False

    def test_returns_none_as_synonym_when_no_synonyms_exists(self):
        assert False

    def test_returns_none_as_derived_term_when_no_derived_terms_exist(self):
        assert False

    def test_returns_correct_definitions_of_a_given_word(self):
        assert False

    def test_returns_the_correct_translations_of_the_definitions(self):
        assert False

    def test_returns_correct_examples_for_each_translation(self):
        assert False

    def test_returns_compound_words_if_they_exists(self):
        return False

    def test_returns_none_as_compund_words_if_none_exists(self):
        return False

    def test_returns_declensions_table_if_it_exists(self):
        return False
