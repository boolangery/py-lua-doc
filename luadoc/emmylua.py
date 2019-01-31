from parsimonious.grammar import Grammar


emmy_lua_type_grammar = Grammar(
    """
    emmy_type_desc = emmy_type_or desc?
    emmy_type_or   = emmy_type s ("|" s emmy_type s)*
    emmy_type      = func / table / type_id
    table          = "table" s "<" s type_id s "," s type_id s ">" s
    func           = "fun" "(" s func_args s ")" s func_return?
    func_return    = ":" s type_id 
    func_args      = func_arg? (s "," s func_arg s)*
    func_arg       = type_id s ":" s emmy_type
    type_id        = (id ("." id)* "[]"?)
    id             = ~"[_a-zA-Z][_a-zA-Z0-9]*"
    desc           = ~".*"
    s              = " "*
    """)


def parse_type_str(input_str: str):
    """
    Validate an emmy lua type descriptor and return a tuple:
    (type, description)
    """
    parse_tree = emmy_lua_type_grammar.parse(input_str)

    if len(parse_tree.children) > 1:
        return parse_tree.children[0].text, parse_tree.children[1].text
    else:
        return parse_tree.children[0].text, ""
