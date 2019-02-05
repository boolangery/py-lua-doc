import luadoc.model as model


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
