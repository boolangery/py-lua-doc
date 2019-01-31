from enum import Enum
from typing import List
import json


class LuaNode:
    pass


class LuaTypes:
    UNKNOWN = 0
    CUSTOM = 1
    STRING = 2
    NUMBER = 3
    INTEGER = 4
    FLOAT = 5
    BOOLEAN = 6
    FUNCTION = 7
    TABLE = 8
    USERDATA = 9


LuaTypes_str = dict([
    (LuaTypes.UNKNOWN, "unknown"),
    (LuaTypes.STRING, "string"),
    (LuaTypes.NUMBER, "number"),
    (LuaTypes.INTEGER, "int"),
    (LuaTypes.FLOAT, "float"),
    (LuaTypes.BOOLEAN, "bool"),
    (LuaTypes.FUNCTION, "func"),
    (LuaTypes.TABLE, "table"),
    (LuaTypes.USERDATA, "userdata")
])


class LuaVisibility:
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"

    def to_json(self):
        return self.value


LuaVisibility_from_str = dict([
    ("public", LuaVisibility.PUBLIC),
    ("protected", LuaVisibility.PROTECTED),
    ("private", LuaVisibility.PRIVATE)
])


class LuaType(LuaNode):
    def __init__(self, name: str):
        self.id = name

    # def to_json(self) -> str:
    #    if self.type is LuaTypes.CUSTOM:
    #        return self.name_if_custom
    #    else:
    #        return LuaTypes_str[self.type]


class LuaTypeNil(LuaType):
    def __init__(self):
        LuaType.__init__(self, "nil")


class LuaTypeBoolean(LuaType):
    def __init__(self):
        LuaType.__init__(self, "boolean")


class LuaTypeNumber(LuaType):
    def __init__(self):
        LuaType.__init__(self, "number")


class LuaTypeString(LuaType):
    def __init__(self):
        LuaType.__init__(self, "string")


class LuaTypeFunction(LuaType):
    def __init__(self):
        LuaType.__init__(self, "function")


class LuaTypeUserdata(LuaType):
    def __init__(self):
        LuaType.__init__(self, "userdata")


class LuaTypeThread(LuaType):
    def __init__(self):
        LuaType.__init__(self, "thread")


class LuaTypeTable(LuaType):
    def __init__(self):
        LuaType.__init__(self, "table")


class LuaTypeAny(LuaType):
    def __init__(self):
        LuaType.__init__(self, "any")


class LuaTypeArray(LuaType):
    def __init__(self, lua_type: LuaType):
        LuaType.__init__(self, "array")
        self.type = lua_type


class LuaTypeCustom(LuaType):
    def __init__(self, name: str):
        LuaType.__init__(self, "custom")
        self.name = name


class LuaTypeDict(LuaType):
    def __init__(self, key_type: LuaType, value_type: LuaType):
        LuaType.__init__(self, "dict")
        self.key_type = key_type
        self.value_type = value_type


class LuaTypeCallable(LuaType):
    def __init__(self, arg_types: List[LuaType], return_types: List[LuaType]):
        LuaType.__init__(self, "callable")
        self.arg_types = arg_types
        self.return_types = return_types


class LuaTypeOr(LuaType):
    """
    Represent a list of possible types.
    e.g: number | string
    """

    def __init__(self, lua_types: List[LuaType]):
        LuaType.__init__(self, "or")
        self.types = lua_types


class LuaParam(LuaNode):
    def __init__(self, name: str, desc: str,
                 lua_type: LuaType = LuaType(LuaTypes.UNKNOWN),
                 is_opt: bool = False):
        self.name = name
        self.desc = desc
        self.type = lua_type
        self.is_opt = is_opt


class LuaReturn(LuaNode):
    def __init__(self, desc: str, lua_type: LuaType = LuaType(LuaTypes.UNKNOWN)):
        self.desc = desc
        self.type = lua_type


class LuaFunction(LuaNode):
    def __init__(self, name: str, short_desc: str = '', desc: str = '', params=None, returns=None):
        LuaNode.__init__(self)

        if returns is None:
            returns = []
        if params is None:
            params = []

        self.name = name
        self.short_desc = short_desc
        self.desc = desc
        self.params = params
        self.returns = returns
        self.usage = ''
        self.is_virtual = False
        self.is_abstract = False
        self.is_deprecated = False
        self.visibility = LuaVisibility.PUBLIC


class LuaClassField(LuaNode):
    def __init__(self, name: str, desc: str,
                 lua_type: LuaType = LuaType(LuaTypes.UNKNOWN),
                 visibility: LuaVisibility = LuaVisibility.PUBLIC):
        self.name = name
        self.desc = desc
        self.type = lua_type
        self.visibility: LuaVisibility = visibility


class LuaClass(LuaNode):
    def __init__(self, name: str = 'unknown', name_in_source: str = ''):
        LuaNode.__init__(self)
        self.name: str = name
        self.name_in_source: str = name_in_source
        self.methods: LuaFunction = []
        self.desc: str = ''
        self.usage: str = ''
        self.inherits_from: List[str] = []  # a list of class.name
        self.fields: List[LuaClassField] = []


class LuaModule(LuaNode):
    def __init__(self, name: str):
        LuaNode.__init__(self)
        # list of LuaStatement
        self.classes = []
        self.functions = []
        self.name = name
        self.isClassMod = False
        self.desc = ''
        self.usage = ''


class LuaQualifier:
    pass


class LuaVirtualQualifier(LuaQualifier):
    def __init__(self):
        LuaQualifier.__init__(self)


class LuaAbstractQualifier(LuaQualifier):
    def __init__(self):
        LuaQualifier.__init__(self)


class LuaDeprecatedQualifier(LuaQualifier):
    def __init__(self):
        LuaQualifier.__init__(self)


class LuaPrivateQualifier(LuaQualifier):
    def __init__(self):
        LuaQualifier.__init__(self)
