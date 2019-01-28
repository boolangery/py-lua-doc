import json
from typing import List
from luadoc.model import *


def to_pretty_str(modules: List[LuaModule]):
    return PythonStyleVisitor().visit(modules)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            to_json = getattr(o, "to_json")
            if callable(to_json):
                return to_json()

        except AttributeError:
            return o.__dict__


def to_pretty_json(modules: List[LuaModule]) -> str:
    return json.dumps(modules, cls=JSONEncoder, indent=4)


class VisitorException(Exception):
    def __init__(self, message):
        self.message = message


def _qualname(obj):
    """Get the fully-qualified name of an object (including module)."""
    return obj.__module__ + '.' + obj.__qualname__


def _declaring_class(obj):
    """Get the name of the class that declared an object."""
    name = _qualname(obj)
    return name[:name.rfind('.')]


# Stores the actual visitor methods
_methods = {}


# Delegating visitor implementation
def _visitor_impl(self, arg):
    """Actual visitor method implementation."""
    if (_qualname(type(self)), type(arg)) in _methods:
        method = _methods[(_qualname(type(self)), type(arg))]
        return method(self, arg)
    else:
        # if no visitor method found for this arg type,
        # search in parent arg type:
        argParentType = arg.__class__.__bases__[0]
        while argParentType != object:
            if (_qualname(type(self)), argParentType) in _methods:
                method = _methods[(_qualname(type(self)), argParentType)]
                return method(self, arg)
            else:
                argParentType = argParentType.__bases__[0]
    raise VisitorException('No visitor found for class ' + str(type(arg)))


# The actual @visitor decorator
def visitor(arg_type):
    """Decorator that creates a visitor method."""

    def decorator(fn):
        declaring_class = _declaring_class(fn)
        _methods[(declaring_class, arg_type)] = fn

        # Replace all decorated methods with _visitor_impl
        return _visitor_impl

    return decorator


class PythonStyleVisitor:
    def __init__(self, indent=2):
        self.indentValue = indent
        self.currentIndent = 0

    def indentStr(self, newLine=True):
        res = ' ' * self.currentIndent
        if newLine:
            res = '\n' + res
        return res

    def indent(self):
        self.currentIndent += self.indentValue

    def dedent(self):
        self.currentIndent -= self.indentValue

    def prettyCount(self, object, isList=False):
        res = ''
        if isinstance(object, list):
            itemCount = len(object)
            res += '[] ' + str(itemCount) + ' '
            if itemCount > 1:
                res += 'items'
            else:
                res += 'item'
        elif isinstance(object, LuaNode):
            if isList:
                return '{} 1 key'
            keyCount = len([attr for attr in object.__dict__.keys() if not attr.startswith("_")])
            res += '{} ' + str(keyCount) + ' '
            if keyCount > 1:
                res += 'keys'
            else:
                res += 'key'
        else:
            res += '[unknow]'
        return res

    @visitor(str)
    def visit(self, node):
        # if node.startswith('"') and node.endswith('"'):
        #     node = node[1:-1]
        return repr(node)

    @visitor(float)
    def visit(self, node):
        return str(node)

    @visitor(int)
    def visit(self, node):
        return str(node)

    @visitor(list)
    def visit(self, obj):
        res = ''
        k = 0
        for itemValue in obj:
            res += self.indentStr() + str(k) + ': ' + self.prettyCount(itemValue, True)
            self.indent()
            res += self.indentStr(False) + self.visit(itemValue)
            self.dedent()
            k += 1
        return res

    @visitor(LuaNode)
    def visit(self, node):
        res = self.indentStr() + node.__class__.__name__ + ': ' + self.prettyCount(node)

        self.indent()

        for attr, attrValue in node.__dict__.items():
            if not attr.startswith(('_', 'comments')):
                if isinstance(attrValue, LuaNode) or isinstance(attrValue, list):
                    res += self.indentStr() + attr + ': ' + self.prettyCount(attrValue)
                    self.indent()
                    res += self.visit(attrValue)
                    self.dedent()
                else:
                    if attrValue is not None:
                        res += self.indentStr() + attr + ': ' + self.visit(attrValue)
        self.dedent()
        return res
