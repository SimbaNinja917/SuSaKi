'''
Created on Apr 22, 2016

@author: simon
'''

import re
import logging
from collections import namedtuple
import json

VerbTypePattern = namedtuple("VerbTypePattern", "pattern, verb_type")
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class VerbConjugator():

    strong_kpt_patterns = [r'(lke|lki|rke|rki|hke|uku|yky)',
                           r'(lk|kk|tt|pp|nk|lp|rp|mp|ht|lt|rt|nt|rk)',
                           r'[^hst](?:k)|(?:p)|[^s](?:t)']

    weak_kpt_patterns = [r'(lje|lje|rje|rje|hje|uvu|yvy)',
                         r'(ng|lv|rv|mm|hd|ll|rr|nn)',
                         r'[^hst](?:k)|(?:p)|[^s](?:t)|v|d|r|l']

    pre_pattern = r'(?=\w*?)'
    post_pattern = r'(?=[aeouiyäö]*$)'

    #pattern_strong = r'(?=\w*?)((?:lke|lki|rke|rki|hke|uku|yky)|(?:lk|kk|tt|pp|nk|lp|rp|mp|ht|lt|rt|nt|rk)|(?:[^hst](?:k)|(?:p)|[^s](?:t)))(?=[aeouiyäö]+$)'

    KPT_dict_strong = {
        'kk': 'k',
        'pp': 'p',
        'tt': 't',
        'k': '',
        'p': 'v',
        't': 'd',
        'rt': 'rr',
        'lt': 'll',
        'nt': 'nn',
        'nk': 'ng',
        'mp': 'mm',
        'lp': 'lv',
        'tp': 'rv',
        'ht': 'hd',
        'rk': 'r',
        'lke': 'lje',
        'lki': 'lje',
        'rke': 'rje',
        'rki': 'rje',
        'hke': 'hje',
        'uku': 'uvu',
        'yky': 'yvy',
        'lk': 'l'}

    def __init__(self):
        self._setup_weak_kpt_dict()
#         with open('dict.txt', 'w') as filehandler:
#             json.dump(self.KPT_dict_strong, filehandler)

    def _setup_weak_kpt_dict(self):
        """ Create the weak kpt dict as a mirror of the string kpt dict"""
        self.KPT_dict_weak = {
            value: key for key, value in self.KPT_dict_strong.items()}

    def conjugate_verb(self, verb, tense):
        """ Conjugate the verb in the given tense"""
        verb_type = self.verb_type(verb)
        if tense == 'present':
            return self._conjugate_present(verb, verb_type)

    def _find_kpt_pattern(self, word, pattern_list):
        """ 
        Using the prioritized list of patterns, return the first 
        match together with its corresponding kpt_pattern.
        """
        for kpt_pattern in pattern_list:
            search_pattern = '{}{}{}'.format(
                self.pre_pattern, kpt_pattern, self.post_pattern)
            match = re.search(search_pattern, word)
            if match:
                return match, kpt_pattern
        return None, None

    def _extract_stem(self, naive_stem, kpt_pattern_list, kpt_pattern_dict):
        """
        Extract the stem grom the naive stem.
        naive_stem: the stem of a word without kpt-changes
        kpt_pattern_list: the prioritized list of kpt-patterns
        kpt_pattern_dict: the kpt-dictionary to use to convert the found kpt-group
                          from string to weak or  weak to strong
        """
        logger.debug(
            'Extracting the infinitive stem using the naïve stem {}'.format(naive_stem))
        match, pattern = self._find_kpt_pattern(naive_stem, kpt_pattern_list)
        if match:
            kpt_group = match.group(0)
            logger.debug('KPT-group found: {}'.format(kpt_group))
            replacement = kpt_pattern_dict[kpt_group]
            logger.debug(
                'Replacement for {} is {}'.format(kpt_group, replacement))
            correct_stem = re.sub(pattern, replacement, naive_stem)
            logger.debug(
                'The correct stem of {} is {}'.format(naive_stem, correct_stem))
        else:
            logger.debug('No kpt-changes in {}'.format(naive_stem))
            correct_stem = naive_stem
        return correct_stem

    def _infinitive_stem(self, verb, verb_type, to_strong=False, to_weak=False):
        """Extract the infinite naive_stem of the verb"""
        if verb_type == 1:
            naive_stem = verb[:-1]
            logger.debug('Naïve stem is {}'.format(naive_stem))
            if to_weak:
                naive_stem = self._extract_stem(
                    naive_stem, self.strong_kpt_patterns, self.KPT_dict_strong)
            return naive_stem

    def _conjugate_present(self, verb, verb_type):
        """Conjugate the given verb in its present form"""
        conjugation_dict = {}
        if verb_type == 1:
            weak_stem = self._infinitive_stem(verb, verb_type, to_weak=True)
            strong_stem = self._infinitive_stem(
                verb, verb_type, to_strong=True)
            conjugation_dict = {'minä': weak_stem + 'n',
                                'sinä': weak_stem + 't',
                                'hän': strong_stem + strong_stem[-1],
                                'me': weak_stem + 'mme',
                                'te': weak_stem + 'tte',
                                'he': strong_stem + 'vat'}
        logger.debug(conjugation_dict)
        return conjugation_dict

    def verb_type(self, verb):
        """
        Reads the given verb and returns the verb type.
        Does not take irregularities into account (verbs that belong to the 'wrong' verb type.
        The verb must be in its infinitive form.
        Verb rules taken from http://people.uta.fi/~km56049/finnish/verbs.html
        """
        logger.debug('Get verb type for {}'.format(verb))
        verb_type_pattern_list = [
            VerbTypePattern(r'[aeiouyäö][aä]$', 1),
            VerbTypePattern(r'd[aä]$', 2),
            VerbTypePattern(r'(?:[lnr]|st)[aä]$', 3),
            VerbTypePattern(r'[aouyäö]t[aä]$', 4),
            VerbTypePattern(r'it[aä]$', 5),
            VerbTypePattern(r'et[aä]$', 6)
        ]

        for verb_type_pattern in verb_type_pattern_list:
            logger.debug(
                'Checking verb type {1} using pattern {0}'.format(*verb_type_pattern))
            if re.search(verb_type_pattern.pattern, verb):
                return verb_type_pattern.verb_type
        return -1


def print_conjugation(conjugation_dict):
    string = 'Minä {minä}\nSinä {sinä}\nHän {hän}\nMe {me}\nTe {te}\nHe {he}'.format(
        **conjugation_dict)
    print(string)

if __name__ == '__main__':
    verb = 'antaa'
    conjugator = VerbConjugator()
    conjugation_dict = conjugator.conjugate_verb(verb, 'present')
    print(conjugation_dict)
    print_conjugation(conjugation_dict)
