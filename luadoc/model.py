from typing import List, TypeVar
from enum import Enum
import luaparser.astnodes as nodes


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


class LuaVisibility(str, Enum):
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"


LuaVisibility_from_str = dict([
    ("public", LuaVisibility.PUBLIC),
    ("protected", LuaVisibility.PROTECTED),
    ("private", LuaVisibility.PRIVATE)
])


class LuaType(LuaNode):
    def __init__(self, name: str):
        self.id = name


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
    def __init__(self, arg_types: List[LuaType], return_types: List[LuaType], arg_names: List[str] = None):
        LuaType.__init__(self, "callable")
        self.arg_types = arg_types
        self.arg_names = arg_names
        self.return_types = return_types

    def to_json(self):
        return {
            "id": self.id,
            "arg_types": self.arg_types,
            "return_types": self.return_types,
        }


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
                 lua_type: LuaType = LuaTypeAny(),
                 is_opt: bool = False):
        self.name = name
        self.desc = desc
        self.type = lua_type
        self.is_opt = is_opt
        self.default_value: any = ""


class LuaReturn(LuaNode):
    def __init__(self, desc: str, lua_type: LuaType = LuaTypeAny()):
        self.desc = desc
        self.type = lua_type


class LuaSourceNode(LuaNode):
    def __init__(self):
        LuaNode.__init__(self)
        self.start_char: int = 0  # character offset
        self.stop_char: int = 0  # character offset

    def init(self, ast_node: nodes.Node):
        self.start_char = ast_node.start_char or 0
        self.stop_char = ast_node.stop_char or 0
        return self


class LuaFunction(LuaSourceNode):
    def __init__(self, name: str, short_desc: str = '', desc: str = '', params=None, returns=None):
        LuaSourceNode.__init__(self)

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
        self.is_static = False
        self.visibility = LuaVisibility.PUBLIC


class LuaClassField(LuaNode):
    def __init__(self, name: str, desc: str,
                 lua_type: LuaType = LuaTypeAny(),
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
        self.methods: List[LuaFunction] = []
        self.short_desc: str = ''
        self.desc: str = ''
        self.usage: str = ''
        self.inherits_from: List[str] = []  # a list of class.name
        self.fields: List[LuaClassField] = []


class LuaModule(LuaNode):
    def __init__(self, name: str):
        LuaNode.__init__(self)
        # list of LuaStatement
        self.file_path: str = ""
        self.classes: List[LuaTypeCallable] = []
        self.functions: List[LuaFunction] = []
        self.data: List[LuaData] = []
        self.name: str = name
        self.is_class_mod: bool = False
        self.short_desc: str = ''
        self.desc: str = ''
        self.usage: str = ''


class LuaData(LuaNode):
    def __init__(self, name: str):
        self.name: str = name
        self.short_desc: str = ""
        self.desc: str = ""
        self.visibility: LuaVisibility = LuaVisibility.PRIVATE
        self.constant: bool = False


class LuaDictField(LuaData):
    def __init__(self, name: str, desc: str):
        LuaData.__init__(self, name)
        self.name: str = name
        self.desc: str = desc


class LuaDict(LuaData):
    def __init__(self, name: str, desc: str):
        LuaData.__init__(self, name)
        self.desc: str = desc
        self.fields: List[LuaDictField] = []

    def to_json(self):
        return {
            "table": self.__dict__
        }


class LuaValue(LuaData):
    def __init__(self, name: str, lua_type: LuaType):
        LuaData.__init__(self, name)
        self.type = lua_type
        self.value: any = None

    def to_json(self):
        return {
            "value": self.__dict__
        }


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


class LuaProtectedQualifier(LuaQualifier):
    def __init__(self):
        LuaQualifier.__init__(self)
