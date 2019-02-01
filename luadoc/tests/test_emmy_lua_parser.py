import unittest
import luadoc.model as model
from luadoc.emmylua import parse_param_field


class ParserTestCase(unittest.TestCase):
    def test_parse_or_expr(self):
        t, desc = parse_param_field("string|number the string")
        self.assertIsInstance(t, model.LuaTypeOr)
        self.assertEqual(desc, "the string")

    def test_parse_table_expr(self):
        t, desc = parse_param_field("table<string, number> the number table")
        self.assertIsInstance(t, model.LuaTypeDict)
        self.assertIsInstance(t.key_type, model.LuaTypeString)
        self.assertIsInstance(t.value_type, model.LuaTypeNumber)
        self.assertEqual(desc, "the number table")

    def test_parse_array_expr(self):
        t, desc = parse_param_field("number[]|string[] some array")
        self.assertIsInstance(t, model.LuaTypeOr)
        self.assertEqual(len(t.types), 2)
        self.assertIsInstance(t.types[0], model.LuaTypeArray)
        self.assertIsInstance(t.types[0].type, model.LuaTypeNumber)
        self.assertIsInstance(t.types[1], model.LuaTypeArray)
        self.assertIsInstance(t.types[1].type, model.LuaTypeString)

    def test_parse_fun_expr(self):
        t, desc = parse_param_field("fun(n: number, s: string) : nil")
        self.assertIsInstance(t, model.LuaTypeCallable)
        self.assertEqual(len(t.arg_types), 2)
        self.assertIsInstance(t.arg_types[0], model.LuaTypeNumber)
        self.assertIsInstance(t.arg_types[1], model.LuaTypeString)
        self.assertEqual(len(t.return_types), 1)
        self.assertIsInstance(t.return_types[0], model.LuaTypeNil)

    def test_parse_fun_nested_expr(self):
        t, desc = parse_param_field("fun(s: string, f: fun(i: number))")
        self.assertIsInstance(t, model.LuaTypeCallable)
        self.assertEqual(len(t.arg_types), 2)
        self.assertIsInstance(t.arg_types[0], model.LuaTypeString)
        self.assertIsInstance(t.arg_types[1], model.LuaTypeCallable)
        self.assertEqual(len(t.arg_types[1].arg_types), 1)
        self.assertIsInstance(t.arg_types[1].arg_types[0], model.LuaTypeNumber)

