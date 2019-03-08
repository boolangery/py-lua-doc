import luadoc.model as model
from parsimonious.grammar import Grammar, NodeVisitor
from typing import List


EMMY_LUA_TYPE_GRAMMAR = Grammar(
    """
    emmy_type_desc = _ emmy_type_or (_ "," _ emmy_type_or)* "@"? desc?
    emmy_type_or   = emmy_type _ ("|" _ emmy_type _)*
    emmy_type      = func / table / array / type_id

    table          = "table" _ "<" _ emmy_type _ "," _ emmy_type _ ">" _
    array          = type_id _ "[]"

    func           = "fun" _ "(" _ func_args? _ ")" _ func_return?
    func_return    = ":" _ emmy_type 
    func_args      = func_arg (_ "," _ func_arg _)*
    func_arg       = func_arg_name ":" _ emmy_type
    func_arg_name  = id _

    type_id        = id ("." id)*
    id             = ~"[_a-zA-Z][_a-zA-Z0-9]*"
    desc           = ~".*"
    _              = " "*
    """)


class FuncContext:
    def __init__(self):
        self.params: List[model.LuaType] = []
        self.param_names: List[str] = []
        self.returns: List[model.LuaType] = []


class EmmyLuaParser:
    def __init__(self):
        self._function_stack: List[FuncContext] = []
        self.types: List[model.LuaType] = []
        self.desc: str = ""

    def visit(self, node):
        enter_visitor = getattr(self, "enter_" + node.expr_name, None)
        if enter_visitor:
            enter_visitor(node, node.children)

        for n in node.children:
            self.visit(n)

        visitor = getattr(self, "visit_" + node.expr_name, None)
        if visitor:
            visitor(node, node.children)

    # noinspection PyUnusedLocal
    def enter_func(self, node, children):
        self._function_stack.append(FuncContext())

    # noinspection PyUnusedLocal
    def visit_func(self, node, children):
        func = model.LuaTypeCallable(arg_types=self._function_stack[-1].params,
                                     return_types=self._function_stack[-1].returns,
                                     arg_names=self._function_stack[-1].param_names)
        self._function_stack.pop()
        self.types.append(func)

    # noinspection PyUnusedLocal
    def visit_func_arg(self, node, children):
        self._function_stack[-1].params.append(self.types.pop())

    # noinspection PyUnusedLocal
    def visit_func_arg_name(self, node, children):
        self._function_stack[-1].param_names.append(node.text.strip())

    # noinspection PyUnusedLocal
    def visit_func_return(self, node, children):
        self._function_stack[-1].returns.append(self.types.pop())

    # noinspection PyUnusedLocal
    def visit_table(self, node, children):
        table = model.LuaTypeDict(self.types[-2], self.types[-1])
        self.types.pop()
        self.types.pop()
        self.types.append(table)

    # noinspection PyUnusedLocal
    def visit_array(self, node, children):
        self.types.append(model.LuaTypeArray(self.types.pop()))

    # noinspection PyUnusedLocal
    def visit_type_id(self, node, children):
        self.types.append(parse_type(node.text))

    # noinspection PyUnusedLocal
    def visit_emmy_type_or(self, node, children):
        if len(self.types) > 1:
            types = model.LuaTypeOr(self.types)
            self.types = [types]

    # noinspection PyUnusedLocal
    def visit_desc(self, node, children):
        self.desc = node.text

    def generic_visit(self, node, children):
        pass


def parse_param_field(input_str: str) -> (model.LuaType, str):
    """
    Try to parse an emmy lua param field:
    param_name MY_TYPE[|other_type] [@comment]
    """
    parse_tree = EMMY_LUA_TYPE_GRAMMAR.parse(input_str)
    parser = EmmyLuaParser()
    parser.visit(parse_tree)
    return parser.types[0], parser.desc


def parse_type(type_str: str) -> model.LuaType:
    if type_str == "nil":
        return model.LuaTypeNil()
    elif type_str in ["bool", "boolean"]:
        return model.LuaTypeBoolean()
    elif type_str in ["number", "int", "float"]:
        return model.LuaTypeNumber()
    elif type_str == "string":
        return model.LuaTypeString()
    elif type_str in ["function", "func", "fun"]:
        return model.LuaTypeFunction()
    elif type_str == "userdate":
        return model.LuaTypeUserdata()
    elif type_str == "thread":
        return model.LuaTypeThread()
    elif type_str == ["table", "tab"]:
        return model.LuaTypeTable()
    elif type_str == "any":
        return model.LuaTypeAny()
    else:
        return model.LuaTypeCustom(type_str)
