import luadoc.model as model
from parsimonious.grammar import Grammar, NodeVisitor
from typing import List

EMMY_LUA_TYPE_GRAMMAR = Grammar(
    """
    emmy_type_desc = emmy_type_or desc?
    emmy_type_or   = emmy_type s ("|" s emmy_type s)*
    emmy_type      = func / table / type_id
    table          = "table" s "<" s type_id s "," s type_id s ">" s
    func           = "fun" "(" s func_args s ")" s func_return?
    func_return    = ":" s type_id 
    func_args      = func_arg? (s "," s func_arg s)*
    func_arg       = func_arg_name s ":" s emmy_type
    func_arg_name  = id s
    type_id        = (id ("." id)* "[]"?)
    id             = ~"[_a-zA-Z][_a-zA-Z0-9]*"
    desc           = ~".*"
    s              = " "*
    """)

# convert emmy lua types to model one
EMMY_TYPE_TO_STD = {
    'string': model.LuaTypes.STRING,
    'number': model.LuaTypes.NUMBER,
    'boolean': model.LuaTypes.BOOLEAN,
    'function': model.LuaTypes.FUNCTION,
    'table': model.LuaTypes.TABLE,
    'userdata': model.LuaTypes.USERDATA,
}


def parse_type_str(input_str: str):
    """
    Validate an emmy lua type descriptor and return a tuple:
    (type, description)
    """
    parse_tree = EMMY_LUA_TYPE_GRAMMAR.parse(input_str)

    if len(parse_tree.children) > 1:
        return parse_tree.children[0].text, parse_tree.children[1].text
    else:
        return parse_tree.children[0].text, ""


def parse_type(type_str: str) -> model.LuaType:
    if type_str in EMMY_TYPE_TO_STD:
        return model.LuaType(EMMY_TYPE_TO_STD[type_str])
    return model.LuaType(model.LuaTypes.CUSTOM, type_str)


def parse_overload(input_str: str) -> model.LuaFunction:
    parser = EmmyLuaFuncParser()
    parser.parse(input_str)
    return parser.get_function()


class EmmyLuaFuncParser(NodeVisitor):
    def __init__(self, strict=True):
        self.grammar = EMMY_LUA_TYPE_GRAMMAR
        self._strict = strict
        self._functions: List[model.LuaFunction] = []
        self._func_params: List[model.LuaParam] = []
        self._func_param_names: List[str] = []
        self._func_returns: List[model.LuaReturn] = []
        self._types: List[model.LuaNode] = []

    def get_function(self) -> model.LuaFunction:
        func = model.LuaFunction("anonymous", params=self._func_params, returns=self._func_returns)

        return func

    # noinspection PyUnusedLocal
    def visit_func(self, node, children):
        self._types.append(parse_type(node.text))

    # noinspection PyUnusedLocal
    def visit_func_arg(self, node, children):
        self._func_params.append(model.LuaParam(self._func_param_names.pop(), "", self._types.pop()))

    # noinspection PyUnusedLocal
    def visit_func_return(self, node, children):
        self._func_returns.append(model.LuaReturn("", self._types.pop()))

    # noinspection PyUnusedLocal
    def visit_type_id(self, node, children):
        self._types.append(parse_type(node.text))

    # noinspection PyUnusedLocal
    def visit_func_arg_name(self, node, children):
        self._func_param_names.append(node.text)

    def generic_visit(self, node, children):
        pass
