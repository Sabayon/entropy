# -*- coding: utf-8 -*-
import os
locale_dir = os.path.realpath(os.path.join(os.getcwd(), "i18n"))
os.environ['TEXTDOMAINDIR'] = locale_dir
import sys
sys.path.insert(0,'.')
sys.path.insert(0,'../')

import unittest
from entropy.i18n import _, change_language
from entropy.output import print_info

class MiscTest(unittest.TestCase):

    def setUp(self):
        self._backup_language = os.environ.get("LANGUAGE", '')
        self._words_to_test = [
            "Yes", "No", "database already exists",
            "Install Set", "wrong md5", "no password specified",
            "Exit",
        ]
        self._assert_map = {
            'de_DE': {
                'Exit': u"Schließen",
                'Yes': u"Ja",
                'No': u"Nein",
                'database already exists': u"Datenbank existiert bereits",
                'no password specified': u'Kein Passwort angegeben',
            },
            'it_IT': {
                'Yes': u"Si",
                'database already exists': u'database gi\xe0 esistente',
                'Install Set': u'Installa Set',
                'wrong md5': u'md5 errato',
                'no password specified': u'nessuna password specificata',
                'Exit': u'Esci',
            },
            'fr_FR': {
                'Yes': u'Oui',
                'wrong md5': u'mauvais md5',
                'no password specified': u'pas de mot de passe sp\xe9cifi\xe9',
                'Exit': u'Quitter',
            },
            'es_ES': {
                'Yes': u"Si",
                'database already exists': u'la base de datos ya existe',
                'Install Set': u'Instalar Set',
                'no password specified': u'no se ha especificado una contrase\xf1a',
                'Exit': u'Salir',
            },
            'nl_NL': {
                'Yes': u"Ja",
                'No': u"Nee",
                'database already exists': u'database bestaat al',
                'Install Set': u'Installeer Set',
                'wrong md5': u'verkeerde md5',
                'no password specified': u'geen wachtwoord opgegeven',
                'Exit': u'Afsluiten',
            },
        }

    def tearDown(self):
        """
        tearDown is run after each test
        """
        change_language(self._backup_language)
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def _assert_word(self, untranslated, translated):
        lang = os.environ.get("LANGUAGE")
        amap = self._assert_map.get(lang)
        self.assert_(amap is not None)
        recorded_value = amap.get(untranslated, untranslated)
        self.assertEqual(recorded_value, translated)

    def __do_print(self):
        for word in self._words_to_test:
            tword = _(word)
            print_info("%s [%s]: %s" % (
                r"test", os.environ.get("LANGUAGE"), tword,))
            self._assert_word(word, tword)

    def test_1_italian(self):
        change_language('it_IT')
        self.__do_print()

    def test_2_french(self):
        change_language('fr_FR')
        self.__do_print()

    def test_3_spanish(self):
        change_language('es_ES')
        self.__do_print()

    def test_4_dutch(self):
        change_language('nl_NL')
        self.__do_print()

    def test_5_german(self):
        change_language('de_DE')
        self.__do_print()

    #def test_i18n_func(self):
    #    pass



if __name__ == '__main__':
    unittest.main()
