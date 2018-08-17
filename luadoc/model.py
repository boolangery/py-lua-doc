from enum import Enum
from typing import List


class LuaNode:
    pass


class LuaTypes(LuaNode):
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


class LuaVisibility(LuaNode):
    PUBLIC = 0
    PROTECTED = 1
    PRIVATE = 2


class LuaType(LuaNode):
    def __init__(self, type: LuaTypes, name_if_custom: str=''):
        self.type = type
        self.name_if_custom = name_if_custom


class LuaParam(LuaNode):
    def __init__(self, name:str, desc:str,
                 type:LuaTypes=LuaType(LuaTypes.UNKNOWN),
                 is_opt:bool=False):
        self.name = name
        self.desc = desc
        self.type = type
        self.is_opt = is_opt


class LuaReturn(LuaNode):
    def __init__(self, desc:str, type:LuaTypes=LuaType(LuaTypes.UNKNOWN)):
        self.desc = desc
        self.type = type


class LuaFunction(LuaNode):
    def __init__(self, name:str, short_desc:str ='', desc:str='', params:List[LuaParam]=[], returns=[]):
        LuaNode.__init__(self)
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


class LuaClass(LuaNode):
    def __init__(self, name:str='unknown', name_in_source:str=''):
        LuaNode.__init__(self)
        self.name = name
        self.name_in_source = name_in_source
        self.methods = []
        self.desc = ''
        self.usage = ''


class LuaModule(LuaNode):
    def __init__(self, name:str):
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
