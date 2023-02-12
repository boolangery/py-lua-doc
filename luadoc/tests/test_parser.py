import os
import unittest
from luadoc.parser import DocParser
from luadoc.printers import to_pretty_json


class ParserTestCase(unittest.TestCase):
    maxDiff = None
    CURRENT_DIR: str = os.path.dirname(__file__)
    SOURCE_ROOT: str = os.path.join(CURRENT_DIR, "source")
    LUA_EXT: str = ".lua"
    JSON_EXT: str = ".json"

    def make_test_from_sources(self, test_name: str):
        tree_filepath = os.path.join(ParserTestCase.SOURCE_ROOT, test_name + ParserTestCase.JSON_EXT)
        lua_file = open(os.path.join(ParserTestCase.SOURCE_ROOT, test_name + ParserTestCase.LUA_EXT), 'r')
        tree_file = open(tree_filepath, 'r')

        lua_source = lua_file.read()
        exp_doc_tree = tree_file.read()

        module = DocParser().build_module_doc_model(lua_source, "")
        json_doc_tree = to_pretty_json(module)
        print(json_doc_tree)

        lua_file.close()
        tree_file.close()

        if os.getenv("UPDATE_FILES"):
            with open(tree_filepath, 'w') as f:
                f.write(json_doc_tree)

        self.assertEqual(exp_doc_tree, json_doc_tree)

    def test_class(self):
        self.make_test_from_sources("class")

    def test_class_module(self):
        self.make_test_from_sources("class_module")

    def test_class_inheritance(self):
        self.make_test_from_sources("class_inheritance")

    def test_emmy_lua_params(self):
        self.make_test_from_sources("emmy_lua_params")

    def test_luadoc_tparam(self):
        self.make_test_from_sources("luadoc_tparam")

    def test_full_module(self):
        self.make_test_from_sources("full_module")

    def test_export_value(self):
        self.make_test_from_sources("export_value")

    def test_explicit_function(self):
        self.make_test_from_sources("explicit_function")

    def test_func_on_table(self):
        self.make_test_from_sources("func_on_table")

    def test_emmy_lua_class(self):
        self.make_test_from_sources("emmy_lua_class")
