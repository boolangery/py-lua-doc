import unittest
from luadoc.parser import parse_emmy_lua_type


class ParserTestCase(unittest.TestCase):
    def test_parser(self):
        emmy_type, desc = parse_emmy_lua_type("fun(processor: fun(data: string,t:table<string, string>))|boolean|int "
                                              "this is a field")
        self.assertEqual(emmy_type, "fun(processor: fun(data: string,t:table<string, string>))|boolean|int ")
        self.assertEqual(desc, "this is a field")

        emmy_type, desc = parse_emmy_lua_type("table < string , Car> desc")
        self.assertEqual(emmy_type, "table < string , Car> ")
        self.assertEqual(desc, "desc")
