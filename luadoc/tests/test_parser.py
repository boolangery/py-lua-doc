import unittest
from luadoc.parser import DocParser
from luadoc.printers import toPrettyStr


class ParserTestCase(unittest.TestCase):
    def test_parser(self):
        src = r'''
            '''
        model = DocParser().build_module_doc_model(src)
        print(toPrettyStr(model))

