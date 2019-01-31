import unittest
from luadoc.emmylua import parse_type_str, parse_overload


class ParserTestCase(unittest.TestCase):
    def test_parser(self):
        emmy_type, desc = parse_type_str("fun(processor: fun(data: string,t:table<string, string>))|boolean|int "
                                              "this is a field")
        self.assertEqual(emmy_type, "fun(processor: fun(data: string,t:table<string, string>))|boolean|int ")
        self.assertEqual(desc, "this is a field")

        emmy_type, desc = parse_type_str("table < string , Car> desc")
        self.assertEqual(emmy_type, "table < string , Car> ")
        self.assertEqual(desc, "desc")

    def test_overload_parser_1(self):
        model = parse_overload("fun(arg1: string, arg2: boolean):pl.List")
        self.assertEqual(model.name, "anonymous")
        self.assertEqual(len(model.params), 2)
        self.assertEqual(model.params[0].name, "arg1")
        self.assertEqual(model.params[1].name, "arg2")

    def test_overload_parser_2(self):
        model = parse_overload("fun(s: string, h: fun()):pl.List")
        self.assertEqual(model.name, "anonymous")
        self.assertEqual(len(model.params), 2)
        self.assertEqual(model.params[0].name, "s")
        self.assertEqual(model.params[1].name, "h")
