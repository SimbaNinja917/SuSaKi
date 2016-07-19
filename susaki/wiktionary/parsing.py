'''
Created on Apr 21, 2016

@author: Simon T. Clement
'''
import re

import logging

from bs4 import BeautifulSoup
from lxml import etree

from susaki.wiktionary.connectors import APIConnector

import argparse
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger('__name__')
logging.getLogger("requests").setLevel(logging.WARNING)


class HTMLParser():
    PARSER = 'html.parser'

    possible_word_classes = ('Verb|Noun|Adjective|Numeral|Pronoun|Adverb|'
                             'Suffix|Conjunction|Determiner|Exclamation|'
                             'Preposition|Postposition|Prefix|Abbreviation|Particle')

    def _extract_soup_between(self, from_tag, to_tag, soup):
        """
        Extract all tags between the from and to tags in the given soup.
        If to_tag is None, all tags from from_tag to the end of the soup are extracted.
        Returns a new soup object of the text between the two tags.
        """
        logger.debug('Extracting soup between two tags')
        logger.debug('From tag: {}'.format(from_tag.name))
        if to_tag:
            name = to_tag.name
        else:
            name = None
        logger.debug('To tag: {}'.format(name))
        tags_between = []
        next_ = from_tag
        while True:
            logger.debug('Appending {}'.format(next_.name))
            tags_between.append(str(next_))
            next_ = next_.nextSibling
            if not next_ or next_ == to_tag:
                break
        soup_text = ''.join(tags_between)
        new_soup = BeautifulSoup(soup_text, self.PARSER)
        return new_soup

    def _extract_inflection_table(self, pos_soup):
        logger.debug('Starting extraction of inflection table')
        inflection_table_soup = pos_soup.find(
            'table',
            attrs={'class': 'inflection-table vsSwitcher vsToggleCategory-inflection'})
        if not inflection_table_soup:
            raise LookupError('No inflection table present')
        else:
            logger.debug('Found inflection table:\n{}'.format(inflection_table_soup))
        return inflection_table_soup

    def _extract_meta_information(self, headline_text):
        """ Extract meta information from the headline text"""
        meta_info = re.match(r' *Inflection of (\w+) \(Kotus type (\d\d?)/(\w+), (.*) gradation\)', headline_text)
        word = meta_info.group(1)
        kotus_type = meta_info.group(2)
        kotus_word = meta_info.group(3)
        gradation = meta_info.group(4)
        logger.debug('Word: {}'.format(word))
        logger.debug('Kotus type: {}'.format(kotus_type))
        logger.debug('Kotus word: {}'.format(kotus_word))
        logger.debug('Gradation {}'.format(gradation))
        return word, kotus_type, kotus_word, gradation

    def _create_meta_tree(self, word, kotus_type, kotus_word, gradation):
        meta_element = etree.Element('meta')
        kotus_element = etree.SubElement(meta_element, 'kotus')
        kotus_type_element = etree.SubElement(kotus_element, 'type')
        kotus_type_element.text = kotus_type
        kotus_word_element = etree.SubElement(kotus_element, 'word')
        kotus_word_element.text = kotus_word
        gradation_element = etree.SubElement(meta_element, 'gradation')
        gradation_element.text = gradation
        word_element = etree.SubElement(meta_element, 'word')
        word_element.text = word
        return meta_element

    def _parse_headline_information(self, headline_row):
        logger.debug('Extracting meta info from table')
        headline_element = headline_row.th
        headline_text = headline_element.text
        logger.debug('Headline text: {}'.format(headline_text))
        word, kotus_type, kotus_word, gradation = self._extract_meta_information(headline_text)
        meta_element = self._create_meta_tree(word, kotus_type, kotus_word, gradation)
        return meta_element

    def _parse_inflection_table(self, table_soup, is_verb=False):
        logger.debug('Parsing inflection table')
        inflection_root = etree.Element('Inflection_Table')
        table_rows = table_soup.find_all('tr', recursive=False)
        logger.debug('Number of table rows: {}'.format(len(table_rows)))
        headline = table_rows[0]
        meta_element = self._parse_headline_information(headline)
        inflection_root.append(meta_element)

        if is_verb:
            table_root = self._parse_inflection_verb_table(table_rows)
        else:
            table_root = self._parse_inflection_noun_table(table_rows)

        inflection_root.append(table_root)
        return inflection_root

    def _clean_table_titles(self, text):
        clean_text = self._clean_text(text)
        if 'tense' in clean_text:
            clean_text = clean_text.split()[0]
        else:
            clean_text = '_'.join(clean_text.split())  # For some reason a simple str.replace didn't work
        return clean_text

    def _create_mood_element(self, row):
        mood = self._clean_table_titles(row.text)
        if mood == 'Nominal_forms':
            raise LookupError('Nominal form')
        mood_element = etree.Element(mood)
        return mood_element

    def _create_tense_elements(self, mood_element, table_headers):
        tense_titles = [
            self._clean_table_titles(table_headers[0].text),
            self._clean_table_titles(table_headers[1].text)
        ]
        logger.debug('Starting on new tense pair: {}'.format(str(tense_titles)))
        tense_elements = [etree.SubElement(mood_element, x)
                          for x in tense_titles]
        element_dict = {}
        for tense in tense_elements:
            for feeling in ['positive', 'negative']:
                feel_element = etree.SubElement(tense, feeling)
                for person in ['singular', 'plural', 'passive']:
                    element_dict[(tense.tag, feeling, person)] = \
                        etree.SubElement(feel_element, person)

        logger.debug('Element dict: {}'.format(str(element_dict)))
        return element_dict, tense_titles

    def _fill_inflection_form_element(self, key, person, is_passive,
                                      element_dict, text):
        if is_passive:
            new_element = element_dict[key]
        else:
            new_element = etree.SubElement(element_dict[key], person)
        new_element.text = text

    def _parse_verb_inflection_row(self, row, person_dict, tense_titles,
                                   table_cells, element_dict):
        logger.debug('table cells: {}'.format(row.text))
        person_title = row.find('th').text
        logger.debug('Dirty title: {}'.format(person_title))
        person_title = self._clean_table_titles(person_title)
        logger.debug('Clean title: {}'.format(person_title))
        person, number = person_dict[person_title]
        logger.debug('title, person, number: {}, {}, {}'.format(
            person_title, person, number))
        is_passive = person == 'passive'

        table_column = 0
        for tense in tense_titles:
            for negation in ['positive', 'negative']:
                key = (tense, negation, number)
                text = table_cells[table_column].text.strip()
                self._fill_inflection_form_element(
                    key, person, is_passive, element_dict, text)
                table_column += 1

    def _extract_active_and_passive_forms(self, cell_values, root_element, offset=1):
        times = ['active', 'passive']
        for i, time in enumerate(times):
            element = etree.SubElement(root_element, time)
            element.text = self._clean_text(cell_values[i + offset].text)

    def _extract_first_two_nominal_form_lines(self, table_rows, row_id, infinitives_element, participles_element):
        names = [
            ['first', 'present'],
            ['long_first', 'past']
        ]
        for i, row in enumerate(table_rows[row_id: row_id + 2]):
            cell_values = row.find_all('td')

            infinitive = etree.SubElement(infinitives_element, names[i][0])
            infinitive.text = self._clean_text(cell_values[0].text)

            participle_element = etree.SubElement(participles_element, names[i][1])
            self._extract_active_and_passive_forms(cell_values, participle_element)

    def _extract_nominal_form_lines_3_to_4(self, table_rows, row_id, infinitives_element, participles_element):
        second_infinitive_element = etree.SubElement(infinitives_element, 'second')
        names = [
            ['inessive', 'instructive'],
            ['agent', 'negative']
        ]
        for i, row in enumerate(table_rows[row_id: row_id + 2]):
            cell_values = row.find_all('td')

            infinitive = etree.SubElement(second_infinitive_element, names[0][i])
            self._extract_active_and_passive_forms(cell_values, infinitive, offset=0)

            participle_element = etree.SubElement(participles_element, names[1][i])
            participle_element.text = self._clean_text(cell_values[2].text)

    def _extract_third_infinitives(self, table_rows, row_id, infinitives_element):
        third_infinitive_element = etree.SubElement(infinitives_element, 'third')
        for i, row in enumerate(table_rows[row_id: row_id + 6]):
            cell_values = row.find_all('td')
            headlines = row.find_all('th')
            if i == 0:
                # First row is special since it also contains the title row for the infinitive
                headlines = list(headlines[1:])
                cell_values = cell_values[:-1]
            name = self._clean_text(headlines[0].text)
            infinitive = etree.SubElement(third_infinitive_element, name)
            self._extract_active_and_passive_forms(cell_values, infinitive, offset=0)

    def _extract_fourth_infinitives(self, table_rows, row_id, infinitives_element):
        fourth_infinitive_element = etree.SubElement(infinitives_element, 'fourth')
        for i, row in enumerate(table_rows[row_id: row_id + 2]):
            cell_values = row.find_all('td')
            headlines = row.find_all('th')
            if i == 0:
                # First row is special since it also contains the title row for the infinitive
                headlines = list(headlines[1:])
            name = self._clean_text(headlines[0].text)
            infinitive = etree.SubElement(fourth_infinitive_element, name)
            text = cell_values[0].text
            infinitive.text = self._clean_text(text)

    def _extract_fifth_infinitives(self, table_rows, row_id, infinitives_element):
        element = etree.SubElement(infinitives_element, 'fifth')
        row = table_rows[row_id]
        cell_values = row.find_all('td')
        text = cell_values[0].text
        element.text = self._clean_text(text)

    def _parse_nominal_forms(self, table_rows, row_id):
        mood_element = etree.Element('nominal_forms')
        infinitives_element = etree.SubElement(mood_element, 'infinitives')
        participles_element = etree.SubElement(mood_element, 'participles')

        # The first couple of lines needs to be done outside a loop since they
        # are too different from the rest

        start_id = row_id + 3
        self._extract_first_two_nominal_form_lines(table_rows, start_id, infinitives_element, participles_element)

        start_id += 2
        self._extract_nominal_form_lines_3_to_4(table_rows, start_id, infinitives_element, participles_element)

        start_id += 2
        self._extract_third_infinitives(table_rows, start_id, infinitives_element)

        start_id += 6
        self._extract_fourth_infinitives(table_rows, start_id, infinitives_element)

        start_id += 2
        self._extract_fifth_infinitives(table_rows, start_id, infinitives_element)

        return mood_element

    def _parse_inflection_verb_table(self, table_rows):
        person_dict = {
            '1st_sing.': ('first', 'singular'),
            '2nd_sing.': ('second', 'singular'),
            '3rd_sing.': ('third', 'singular'),
            '1st_plur.': ('first', 'plural'),
            '2nd_plur.': ('second', 'plural'),
            '3rd_plur.': ('third', 'plural'),
            'passive': ('passive', 'passive')
        }
        logger.debug('Inflection table type: verb')
        table_root = etree.Element('table')
        tense_titles = []
        element_dict = {}
        for i, row in enumerate(table_rows[1:]):
            # Figure out which kind of line we have
            table_headers = row.find_all('th', recursive=False)
            table_cells = row.find_all('td', recursive=False)
            num_table_headers = len(table_headers)
            num_table_cells = len(table_cells)
            logger.debug('Number of headers: {}'.format(num_table_headers))
            logger.debug('Number of table cells: {}'.format(num_table_cells))
            if num_table_cells > 0:
                self._parse_verb_inflection_row(
                    row, person_dict, tense_titles, table_cells, element_dict)
            elif num_table_headers == 1:
                # New mood
                try:
                    mood_element = self._create_mood_element(row)
                except LookupError as err:
                    if str(err) == 'Nominal form':
                        nominal_forms_element = self._parse_nominal_forms(table_rows, i + 1)
                        table_root.append(nominal_forms_element)
                        logger.debug('Got to the nominal forms. Breaking')
                        break
                    else:
                        raise
                else:
                    # New mood
                    table_root.append(mood_element)
                    logger.debug('Parsing new mood: {}'.format(
                        mood_element.text))

            elif num_table_headers == 2:
                # New tenses
                element_dict, tense_titles = self._create_tense_elements(
                    mood_element, table_headers)

            elif num_table_headers == 6:
                logger.debug('Header row')
                pass
        return table_root

    def _parse_second_accusative_row(self, noun_case_element, row):
        noun_case_element = noun_case_element.getparent()
        noun_case_element = etree.SubElement(noun_case_element, 'genitive')
        noun_case_element.text = self._clean_text(row.find('td').text)

    def _parse_noun_table_row(self, row, noun_case_element, noun_case_name):
        """Extracts the singular and plural form from the table row"""
        row_elements = row.find_all('td')
        singular = row_elements[0].text
        if noun_case_name == 'genitive':
            logger.debug('Entering genitive case')
            plural = self._clean_text(row_elements[1].find('span').text)
        else:
            plural = self._clean_text(row_elements[1].text)
        singular_element = etree.SubElement(noun_case_element, 'singular')
        singular_element.text = self._clean_text(singular)
        plural_element = etree.SubElement(noun_case_element, 'plural')
        plural_element.text = self._clean_text(plural)

    def _parse_inflection_noun_table(self, table_rows):
        logger.debug('Inflection table type: noun')
        table_root = etree.Element('table')
        in_accusative = False
        noun_case_element = None
        has_seen_table_headers = False
        for row in table_rows[1:]:
            logger.debug('parsing new row')
            noun_case_name = row.th.text
            noun_case_name = self._clean_text(noun_case_name)
            if in_accusative:
                logger.debug('Entering second accusative line')
                self._parse_second_accusative_row(noun_case_element, row)
                in_accusative = False
            else:
                try:
                    logger.debug('Creating new noun case element: {}'.format(
                        noun_case_name))
                    noun_case_element = etree.Element(noun_case_name)
                except ValueError as err:
                    if str(err) == 'Empty tag name':
                        # We hit the table headers
                        logger.debug('Found the table headers\n')
                        has_seen_table_headers = True
                else:
                    if has_seen_table_headers:
                        table_root.append(noun_case_element)
                        if noun_case_name == 'accusative':
                            logger.debug('Found the accusative case')
                            in_accusative = True
                            noun_case_element = etree.SubElement(
                                noun_case_element, 'nominative')
                        self._parse_noun_table_row(
                            row, noun_case_element, noun_case_name)
            logger.debug('\n{}'.format(etree.tostring(
                table_root, encoding='unicode', pretty_print=True)))
        logger.debug('Finished parsing inflection table')
        return table_root

    def _extract_translations(self, pos_soup):
        """Extracts all translations from the given part-of-speech soup"""
        logger.debug('Starting extraction of translations')
        translation_list = pos_soup.find('ol')
        try:
            translations = translation_list.find_all('li', recursive=False)
        except AttributeError:
            raise LookupError('No translations present')
        num_translations = len(translations)
        if num_translations == 0:
            raise LookupError('No translations present')
        logger.debug('Translations found: {}'.format(num_translations))
        return translations

    def _clean_text(self, text):
        clean = text.replace('\n', '')
        clean = clean.strip()
        clean = re.sub(r'  *', ' ', clean)
        return clean

    def _parse_example(self, example_soup):
        logging.debug('Start example parsing on following soup:\n{}\n'.format(example_soup))
        example_part_root = etree.Element('Examples')
        example_elements = example_soup.find_all(
            re.compile('dd|li'), recursive=False)
        logger.debug('Found {} example elements'.format(len(example_elements)))
        for example in example_elements:
            logger.debug('Parsing the following example element:\n{}'.format(example))
            example_root = etree.Element('Example')
            example_part_root.append(example_root)
            example_translation = example.find('dl')
            logger.debug('Example translation:\n{}\n'.format(example_translation))
            try:
                example_translation_text = example_translation.text
            except AttributeError:
                # Example is placed as a quotation insted of a standard example
                logger.debug('Quotation example:\n{}'.format(example))
                example_text = example.text
            else:
                example_translation_text_clean = self._clean_text(
                    example_translation_text)
                # Remove translation to avoid having it show up in the example text
                example_translation.clear()
                example_text = example.text
                example_translation_element = etree.Element('Translation')
                example_translation_element.text = example_translation_text_clean
                example_root.append(example_translation_element)

            example_text_clean = self._clean_text(example_text)
            example_text_element = etree.Element('Text')
            example_text_element.text = example_text_clean
            example_root.append(example_text_element)

        example_soup.clear()
        return example_part_root

    def _parse_translation(self, translation_soup):
        logger.debug('Parsing translation part')
        root = etree.Element('Translation')
        example_part = translation_soup.find(re.compile('dl|ul'))
        if example_part:
            example_part_root = self._parse_example(example_part)
            root.append(example_part_root)
        text = translation_soup.text
        text_clean = self._clean_text(text)
        text_element = etree.Element('Text')
        text_element.text = text_clean
        root.append(text_element)
        return root

    def _parse_POS(self, pos_part):
        pos_type = pos_part.find('span', {'class': 'mw-headline'}).text
        pos_root = etree.Element(pos_type)
        translations_root = etree.Element('Translations')
        pos_root.append(translations_root)
        translation_parts = self._extract_translations(pos_part)
        for translation_part in translation_parts:
            translation_element = self._parse_translation(translation_part)
            translations_root.append(translation_element)
        try:
            inflection_table = self._extract_inflection_table(pos_part)
        except LookupError as err:
            logger.debug("Didn't find an inflection table")
            if str(err) == 'No inflection table present':
                pass
            else:
                raise
        else:
            logger.debug('Found a {} inflection table'.format(pos_type))
            is_verb = 'Verb' in pos_type
            logger.debug('Table is a verb table: {}'.format(is_verb))
            table_element = self._parse_inflection_table(inflection_table, is_verb)
            pos_root.append(table_element)
        return pos_root

    def _get_pos_header_level(self, pos_tag_headers):
        header_levels = {header.name for header in pos_tag_headers}
        if len(header_levels) != 1:
            raise ValueError('The POS-parts are placed at different header levels')
        pos_header_level = header_levels.pop()[1]
        return pos_header_level

    def _tag_ends_pos_part(self, tag, pos_tag_header_level):
        if not re.match(r'^h\d$', str(tag.name)):
            return False
        elif tag.name[1] > pos_tag_header_level:
            return False
        else:
            return True

    def _extract_pos_parts(self, language_part):
        logger.debug('Starting extraction of POS-parts')
        pos_tags = language_part.find_all(
            text=re.compile(self.possible_word_classes),
            attrs={'class': 'mw-headline'})
        num_pos_tags = len(pos_tags)
        if num_pos_tags == 0:
            logger.debug("No POS-parts present")
            raise LookupError('No POS-parts present')
        logger.debug('Number of POS-tags in language part: {}'.format(num_pos_tags))
        pos_tag_headers = [tag.parent for tag in pos_tags]
        pos_tag_header_level = self._get_pos_header_level(pos_tag_headers)
        pos_parts = []
        start_tag = pos_tag_headers[0]
        for tag in start_tag.next_siblings:
            if start_tag and self._tag_ends_pos_part(tag, pos_tag_header_level):
                logger.debug('Tag {} ends current pos part'.format(tag.name))
                pos_part = self._extract_soup_between(start_tag, tag, language_part)
                pos_parts.append(pos_part)
                start_tag = None
            tag_starts_new_pos_part = tag in pos_tag_headers
            if tag_starts_new_pos_part:
                logger.debug('Tag {} starts a new pos part'.format(tag.name))
                start_tag = tag
        if start_tag:
            logger.debug('No tag to end last pos part. '
                         'Extract from last start tag to end of language part')
            pos_part = self._extract_soup_between(start_tag, None, language_part)
            pos_parts.append(pos_part)
        logger.debug('Found {} POS-tags in language part'.format(len(pos_parts)))
        logger.debug('Finished extraction of POS-parts')
        return pos_parts

    def _extract_language_part(self, raw_article, language):
        logger.debug('Starting language part extraction')
        language_header_tags = raw_article.find_all('h2')
        start_tag = None
        end_tag = None
        logger.debug('Number of language headers: {}'.format(
            len(language_header_tags)))
        for i, language_header in enumerate(language_header_tags):
            logger.debug('Checking header {}'.format(i))
            target_language_found = language_header.find(
                'span', {'class': 'mw-headline', 'id': language})
            if target_language_found:
                start_tag = language_header
                logger.debug('Start tag found')
                try:
                    end_tag = language_header_tags[i + 1]
                    logger.debug('End tag found')
                except IndexError:
                    logger.debug('No end tag found')
                    pass
                finally:
                    break
        if not start_tag:
            raise LookupError(
                'No explanations exists for the language: {}'.format(language))
        language_part = self._extract_soup_between(start_tag, end_tag, raw_article)
        logger.debug("Finished language part extraction")
        return language_part

    def parse_article(self, raw_article, word, language='Finnish'):
        """
        raw_article: html-document of the whole article for the word.
            Must have the same format as that returned by the Wiktionary API
        word: the word this article is about
        language: source language of the word.
            This language is used to do the translation into English
        """
        logger.debug('Parsing article')
        article_root = etree.Element('Article')
        word_element = etree.Element('Word')
        word_element.text = word
        article_root.append(word_element)

        languages_root = etree.Element('Languages')
        article_root.append(languages_root)
        language_element = etree.Element(language)
        languages_root.append(language_element)

        raw_soup = BeautifulSoup(raw_article, self.PARSER)
        language_part = self._extract_language_part(raw_soup, language)

        pos_parts = self._extract_pos_parts(language_part)
        pos_parts_root = etree.Element('POS-parts')
        language_element.append(pos_parts_root)
        for pos_part in pos_parts:
            pos_part_element = self._parse_POS(pos_part)
            pos_parts_root.append(pos_part_element)

        return article_root


def print_translations(article_root):
    language_part = article_root.find('Languages').find('Finnish')
    pos_parts = language_part.find('POS-parts')
    for pos in pos_parts:
        print('\n   {}'.format(pos.tag))
        translations = pos.find('Translations')
        for translation in translations:
            print('')
            text = translation.find('Text')
            print('      - ' + text.text)
            examples = translation.find('Examples')
            try:
                for example in examples:
                    print('        * ' + example.find('Text').text)
                    try:
                        print('          ' + example.find('Translation').text)
                    except AttributeError:
                        pass
            except TypeError:
                pass


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        description='Look for translations into English on wiktionary')
    arg_parser.add_argument('word')
    args = arg_parser.parse_args()
    word = args.word
    connector = APIConnector()
    content_text = connector.collect_raw_article(word)
    parser = HTMLParser()
    article_root = parser.parse_article(content_text, word)
    # s = etree.tostring(article_root, pretty_print=True, encoding='unicode')
    # print(s)
    print_translations(article_root)
    s = etree.tostring(article_root, pretty_print=True, encoding='unicode')
    print(s)
