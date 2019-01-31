import luadoc.model as model
from parsimonious.grammar import Grammar, NodeVisitor
from typing import List

EMMY_LUA_TYPE_GRAMMAR = Grammar(
    """
    emmy_type_desc = emmy_type_or (s "," s emmy_type_or)* desc?

    emmy_type_or   = emmy_type s ("|" s emmy_type s)*
    emmy_type      = func / table / array / type_id
    table          = "table" s "<" s type_id s "," s type_id s ">" s
    func           = "fun" "(" s func_args? s ")" s func_return?
    func_return    = ":" s type_id 
    func_args      = func_arg (s "," s func_arg s)*
    func_arg       = func_arg_name s ":" s emmy_type
    func_arg_name  = id s
    array          = type_id s "[]"
    type_id        = id ("." id)*
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


class EmmyLuaParser(NodeVisitor):
    def __init__(self, strict=True):
        self.grammar = EMMY_LUA_TYPE_GRAMMAR
        self._strict = strict
        self._functions: List[model.LuaTypeCallable] = []
        self._func_params: List[model.LuaType] = []
        self._func_returns: List[model.LuaType] = []
        self._func_arg_count_stack: List[int] = [0]
        self.types: List[model.LuaType] = []
        self.desc: str = ""


    # noinspection PyUnusedLocal
    def visit_func(self, node, children):
        func = model.LuaTypeCallable(arg_types=self._func_params, return_types=self._func_returns)
        self._func_params = []
        self._func_returns = []
        self.types.append(func)

    # noinspection PyUnusedLocal
    def visit_func_arg(self, node, children):
        self._func_arg_count_stack[-1] = self._func_arg_count_stack[-1] + 1
        self._func_params.append(self.types.pop())

    # noinspection PyUnusedLocal
    def visit_func_args(self, node, children):
        self._func_arg_count_stack.append(0)

    # noinspection PyUnusedLocal
    def visit_func_return(self, node, children):
        self._func_returns.append(self.types.pop())

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
    parser = EmmyLuaParser()
    parser.parse(input_str)
    return parser.types[0], parser.desc


def parse_type_str(input_str: str) -> (model.LuaType, str):
    """
    Validate an emmy lua type descriptor and return a tuple:
    (type, description)
    """
    parse_tree = EMMY_LUA_TYPE_GRAMMAR.parse(input_str)

    parser = EmmyLuaTypesParser()
    parser.parse(input_str)
    type = parse_type(parser.types[0])

    return type, parser.desc


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
