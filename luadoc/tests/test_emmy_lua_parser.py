import unittest
from luadoc.parser import parse_emmy_lua_type


class ParserTestCase(unittest.TestCase):
    def test_class(self):
        emmy_type, desc = parse_emmy_lua_type("fun(processor: fun(data: string))|boolean|int this is a field")
        self.assertEqual(emmy_type, "fun(processor: fun(data: string))|boolean|int ")
        self.assertEqual(desc, "this is a field")
