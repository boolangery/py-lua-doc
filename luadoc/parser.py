import re
import logging
from luaparser import ast
from luaparser.astnodes import *
from luadoc.model import *
from typing import List, Dict, cast, Callable
import luadoc.emmylua as emmylua
import luadoc.luadoc as luadoc
import luadoc.astutils as astutils


class DocOptions:
    def __init__(self):
        self.comment_prefix = '---'
        self.emmy_lua_syntax = True
        self.private_prefix = "_"
        self.encoding = "utf8"


class SyntaxException(Exception):
    pass


# some custom types
DocTagHandler = Dict[str, Callable[[str, Node], LuaNode or None]]


class LuaDocParser:
    """ Lua doc style parser
    """

    FUNCTION_RE = re.compile(r'^(\w+(:|.)\w+)')
    # match: MY_TYPE: PARENT_TYPE @comment
    # match: MY_TYPE: PARENT_TYPE, TYPE2 comment
    DOC_CLASS_RE = re.compile(r'^([\w.]+)(?:\s*:\s*([\w.]+(?:\s*,\s*[\w.]+)*))?\s*@?(.*)$')
    PARAM_RE = re.compile(r'^(\w+) *([\w+|]+) *(.*)')

    def __init__(self, options: DocOptions, file_path: str):
        self._start_symbol: str = options.comment_prefix
        self.file_path = file_path

        # list of string with no tag
        self._pending_str: List[str] = []
        self._pending_param: List[LuaParam] = []
        self._pending_return: List[LuaReturn] = []
        self._pending_function: List[LuaFunction] = []
        self._pending_qualifiers: List[LuaQualifier] = []  # @virtual, @abstract, @deprecated
        self._pending_class: List[LuaClass] = []
        self._pending_module: List[LuaModule] = []
        self._pending_overload: List[LuaTypeCallable] = []
        self._pending_data: List[LuaData] = []
        self._usage_in_progress: bool = False
        self._usage_str: List[str] = []
        self._exported: bool = False  # comment contains an @export tag ?
        self._constant: bool = False  # is the expression constant ?
        self._namespace: str = ""  # put into namespace ?

        # install handlers
        self._handlers: DocTagHandler = {
            '@abstract': self._parse_abstract,
            '@class': self._parse_class,
            '@classmod': self._parse_class_mod,
            '@constant': self._parse_constant,
            '@deprecated': self._parse_deprecated,
            '@export': self._parse_export,
            '@field': self._parse_class_field,
            '@function': self._parse_function,
            '@int': self._parse_int_param,
            '@module': self._parse_module,
            '@namespace': self._parse_namespace,
            '@overload': self._parse_overload,
            '@param': self._parse_emmy_lua_param if options.emmy_lua_syntax else self._parse_param,
            '@private': self._parse_private,
            '@protected': self._parse_protected,
            '@return': self._parse_emmy_lua_return if options.emmy_lua_syntax else self._parse_return,
            '@string': self._parse_string_param,
            '@tparam': self._parse_tparam,
            '@treturn': self._parse_treturn,
            '@type': self._parse_type,
            '@usage': self._parse_usage,
            '@virtual': self._parse_virtual,
            "@vararg": self._parse_varargs,
        }

        # some regex handler that will be tested after _handlers
        self._re_handler: DocTagHandler = {
            r'^@tparam\[opt(?:\s*=\s*([^\].]*))?\]': self._parse_tparam_opt_re
        }

        self._param_type_str_to_lua_types = {
            'string': LuaTypes.STRING,
            'number': LuaTypes.NUMBER,
            'int': LuaTypes.INTEGER,
            'float': LuaTypes.FLOAT,
            'bool': LuaTypes.BOOLEAN,
            'boolean': LuaTypes.BOOLEAN,
            'function': LuaTypes.FUNCTION,
            'func': LuaTypes.FUNCTION,
            'tab': LuaTypes.TABLE,
            'table': LuaTypes.TABLE,
        }

    def _get_short_desc_and_desc(self) -> (str, str):
        if self._pending_str:
            short_desc = self._pending_str.pop(0)
        else:
            short_desc = ''
        long_desc = '\n'.join(self._pending_str)
        return short_desc, long_desc

    def parse_comments(self, ast_node: Node):
        comments = [c.s for c in ast_node.comments]

        # reset pending list
        self._pending_str = []
        self._pending_param = []
        self._pending_function = []
        self._pending_return = []
        self._pending_qualifiers = []
        self._pending_class = []
        self._pending_module = []
        self._usage_in_progress = False
        self._usage_str = []
        self._pending_overload = []
        self._pending_data = []
        self._exported = False
        self._constant = False

        doc_nodes: List[LuaNode] = []
        for comment in comments:
            node = self._parse_comment(comment, ast_node)
            if node is not None:
                doc_nodes.append(node)

        if self._exported:
            if (isinstance(ast_node, LocalFunction) or
                isinstance(ast_node, Function)) and not self._pending_function:
                function_name = astutils.get_identifier(ast_node)
                short_desc, desc = self._get_short_desc_and_desc()
                func = LuaFunction(name=function_name, short_desc=short_desc, desc=desc).init(ast_node)
                self._pending_function.append(func)
                doc_nodes.append(func)

        # pending data
        if self._pending_data:
            lua_data: LuaData = self._pending_data[-1]
            short_desc, desc = self._get_short_desc_and_desc()
            lua_data.short_desc = short_desc
            lua_data.desc = desc

            if self._exported:
                lua_data.visibility = LuaVisibility.PUBLIC

            lua_data.constant = self._constant

        # pending class
        if self._pending_class:
            lua_class: LuaClass = self._pending_class[-1]
            short_desc, long_desc = self._get_short_desc_and_desc()
            lua_class.short_desc = short_desc
            lua_class.desc = long_desc
            lua_class.usage = '\n'.join(self._usage_str)

        if self._pending_function and self._pending_str:
            short_desc, long_desc = self._get_short_desc_and_desc()
            self._pending_function[-1].short_desc = short_desc
            self._pending_function[-1].desc = long_desc

        # handle pending doc_nodes
        if self._pending_param or self._pending_return or self._pending_qualifiers:
            # methods
            if type(ast_node) == Method:
                short_desc, long_desc = self._get_short_desc_and_desc()
                doc_nodes.append(LuaFunction('', short_desc, long_desc, [], self._pending_return).init(ast_node))

            # Detect static method: a Function with an Index as name
            if type(ast_node) == Function:
                short_desc, long_desc = self._get_short_desc_and_desc()
                doc_nodes.append(LuaFunction('', short_desc, long_desc, [], self._pending_return).init(ast_node))

        # handle function pending elements
        if doc_nodes and type(doc_nodes[-1]) is LuaFunction:
            func: LuaFunction = cast(LuaFunction, doc_nodes[-1])

            # handle pending qualifiers
            if self._pending_qualifiers:
                for qualifier in self._pending_qualifiers:
                    if type(qualifier) is LuaVirtualQualifier:
                        cast(LuaVirtualQualifier, doc_nodes[-1]).is_virtual = True
                    elif type(qualifier) is LuaAbstractQualifier:
                        cast(LuaAbstractQualifier, doc_nodes[-1]).is_abstract = True
                    elif type(qualifier) is LuaDeprecatedQualifier:
                        cast(LuaDeprecatedQualifier, doc_nodes[-1]).is_deprecated = True
                    elif type(qualifier) is LuaPrivateQualifier:
                        func.visibility = LuaVisibility.PRIVATE
                    elif type(qualifier) is LuaProtectedQualifier:
                        func.visibility = LuaVisibility.PROTECTED

            # handle pending usage
            if self._usage_in_progress:
                func.usage = '\n'.join(self._usage_str)

            if self._pending_param:
                func.params.extend(self._pending_param)
                self._pending_param = []

            for overload in self._pending_overload:
                doc_nodes.append(self._create_function_overload(func, overload))

        # handle module pending elements
        if self._pending_module:
            lua_module: LuaModule = self._pending_module[-1]
            if self._usage_str:
                lua_module.usage = '\n'.join(self._usage_str)
            short_desc, desc = self._get_short_desc_and_desc()
            lua_module.short_desc = short_desc
            lua_module.desc = desc

        if self._namespace:
            if self._pending_class:
                self._pending_class[-1].name = ".".join([self._namespace, self._pending_class[-1].name])
            if self._pending_function:
                self._pending_function[-1].name = ".".join([self._namespace, self._pending_function[-1].name])
            if self._pending_data:
                self._pending_data[-1].name = ".".join([self._namespace, self._pending_data[-1].name])

        return doc_nodes, self._pending_str

    # noinspection PyMethodMayBeStatic
    def _create_function_overload(self, original: LuaFunction, overload_def: LuaTypeCallable) -> LuaFunction:
        overload = LuaFunction(name=original.name, short_desc=original.short_desc, desc=original.desc)
        overload.usage = original.usage
        overload.is_virtual = original.is_virtual
        overload.is_abstract = original.is_abstract
        overload.is_deprecated = original.is_deprecated
        overload.visibility = original.visibility

        # add original param from original function only if it exists overloaded def.
        for param in original.params:
            if param.name in overload_def.arg_names:
                overload.params.append(param)

        overload.returns.extend(original.returns)

        return overload

    def _parse_comment(self, comment: str, ast_node: Node):
        if comment.startswith(self._start_symbol):
            text = comment.lstrip(self._start_symbol + " ")
            parts = text.split(" ", 1)
            if parts:
                if parts[0].startswith('@'):
                    if parts[0] in self._handlers:
                        return self._handlers[parts[0]](parts[1].strip() if len(parts) > 1 else "", ast_node)
                    else:
                        for regex, re_handler in self._re_handler.items():
                            m = re.match(regex, parts[0])
                            if m:
                                re_handler(parts[1].strip() if len(parts) > 1 else "", ast_node, m)
                elif not self._usage_in_progress:
                    # its just a string
                    self._pending_str.append(text)
                else:
                    self._usage_str.append(comment[len(self._start_symbol) + 1:])
        return None

    # noinspection PyUnusedLocal
    def _parse_class(self, params: str, ast_node: Node):
        """
        --@class MY_TYPE[:PARENT_TYPE] [@comment]
        """
        match = LuaDocParser.DOC_CLASS_RE.search(params)

        if match:
            main_class, raw_bases, desc = match.groups()

            main_class = LuaClass(main_class, main_class)

            if raw_bases:  # has base class
                bases = [x.strip() for x in raw_bases.split(',')]
                main_class.inherits_from = bases

            self._pending_class.append(main_class)

            return main_class
        else:
            self._report_error(ast_node, "invalid @class tag: @class %s", params)

    # noinspection PyUnusedLocal
    def _parse_usage(self, params: str, ast_node: Node):
        """
        usage must be valid lua source code
        """
        self._usage_in_progress = True

    # noinspection PyUnusedLocal
    def _parse_module(self, params: str, ast_node: Node):
        lua_module = LuaModule(params)
        self._pending_module.append(lua_module)
        return lua_module

    # noinspection PyUnusedLocal
    def _parse_namespace(self, params: str, ast_node: Node):
        self._namespace = params

    # noinspection PyUnusedLocal
    def _parse_overload(self, params: str, ast_node: Node):
        # noinspection PyBroadException
        try:
            model, desc = emmylua.parse_param_field(params)
            self._pending_overload.append(model)
        except Exception as e:
            self._report_error(ast_node, "invalid @overload field: @overload %s", params)

    # noinspection PyUnusedLocal
    def _parse_class_mod(self, params: str, ast_node: Node) -> LuaModule:
        module = LuaModule(params)
        module.is_class_mod = True
        module.desc = '\n'.join(self._pending_str)

        if self._usage_in_progress:
            module.usage = '\n'.join(self._usage_str)
            self._usage_in_progress = False

        self._pending_module.append(module)

        return module

    # noinspection PyUnusedLocal
    def _parse_constant(self, params: str, ast_node: Node):
        self._exported = True  # @constant trigger @export
        self._constant = True

    # noinspection PyMethodMayBeStatic
    def _parse_visibility(self, string: str) -> LuaVisibility:
        if string in LuaVisibility_from_str:
            return LuaVisibility_from_str[string]
        else:
            raise ValueError("invalid visibility string " + string)

    # noinspection PyUnusedLocal
    def _parse_tparam(self, params: str, ast_node: Node, is_opt: bool = False, default_value: str = ""):
        parts = params.split()

        if len(parts) > 2:
            lua_type = luadoc.parse_type(parts[0])
            name = parts[1]
            desc = ' '.join(parts[2:])

            param = LuaParam(name, desc, lua_type, is_opt)
            param.default_value = default_value

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            self._report_error(ast_node, "invalid @tparam tag: @tparam %s", params)

    # noinspection PyUnusedLocal
    def _parse_tparam_opt_re(self, params: str, ast_node: Node, match):
        self._parse_tparam(params, ast_node, True, str(match.group(1)))

    # noinspection PyUnusedLocal
    def _parse_param(self, params: str, ast_node: Node):
        parts = params.split()
        if len(parts) > 1:
            param = LuaParam(parts[0], ' '.join(parts[1:]))
            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            self._report_error(ast_node, "invalid @param tag: @param %s", params)

    # noinspection PyUnusedLocal
    def _parse_emmy_lua_param(self, params: str, ast_node: Node):
        """
        param_name MY_TYPE[|other_type] [@comment]
        """
        # noinspection PyBroadException
        try:
            parts = params.split(' ', 1)
            param_name = parts[0]
            params = parts[1]
            doc_type, desc = emmylua.parse_param_field(params)
            param = LuaParam(param_name, desc, doc_type)
            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        except Exception:
            self._report_error(ast_node, "invalid @param tag: @param %s", params)

    def _parse_string_param(self, params: str, ast_node: Node):
        self._parse_tparam("string " + params, ast_node)

    def _parse_int_param(self, params: str, ast_node: Node):
        self._parse_tparam("int " + params, ast_node)

    # noinspection PyUnusedLocal
    def _parse_treturn(self, params: str, ast_node: Node):
        parts = params.split()

        if len(parts) >= 2:
            lua_type = luadoc.parse_type(parts[0])
            desc = ' '.join(parts[1:])

            param = LuaReturn(desc, lua_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            self._report_error(ast_node, "invalid @treturn tag: @treturn %s", params)

    # noinspection PyUnusedLocal
    def _parse_type(self, params: str, ast_node: Node):
        """
        --@type MY_TYPE [@comment]
        """
        # noinspection PyBroadException
        try:
            identifier = astutils.get_identifier(ast_node)
            value = astutils.get_value(ast_node)
            doc_type, desc = emmylua.parse_param_field(params)
            lua_data = LuaValue(identifier, doc_type)
            lua_data.value = value
            self._pending_data.append(lua_data)
            return lua_data
        except Exception as e:
            self._report_error(ast_node, "invalid @type tag: @type %s", params)

    # noinspection PyUnusedLocal
    def _parse_return(self, params: str, ast_node: Node):
        parts = params.split()

        if len(parts) > 1:
            desc = ' '.join(parts[0:])

            param = LuaReturn(desc)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            self._report_error(ast_node, "invalid @return tag: @return %s", params)

    # noinspection PyUnusedLocal
    def _parse_emmy_lua_return(self, params: str, ast_node: Node):
        # noinspection PyBroadException
        try:
            doc_type, desc = emmylua.parse_param_field(params)
            lua_return = LuaReturn(desc, doc_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(lua_return)
            else:
                self._pending_return.append(lua_return)
        except Exception:
            self._report_error(ast_node, "invalid @return tag: @return %s", params)

    # noinspection PyUnusedLocal
    def _parse_virtual(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].is_virtual = True
        else:
            self._pending_qualifiers.append(LuaVirtualQualifier())

    # noinspection PyUnusedLocal
    def _parse_varargs(self, params: str, ast_node: Node):
        # noinspection PyBroadException
        try:
            doc_type, desc = emmylua.parse_param_field(params)
            param = LuaParam("...", desc, doc_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        except Exception:
            self._report_error(ast_node, "invalid @param tag: @param %s", params)

    # noinspection PyUnusedLocal
    def _parse_abstract(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].is_abstract = True
        else:
            self._pending_qualifiers.append(LuaAbstractQualifier())

    # noinspection PyUnusedLocal
    def _parse_deprecated(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].is_deprecated = True
        else:
            self._pending_qualifiers.append(LuaDeprecatedQualifier())

    # noinspection PyUnusedLocal
    def _parse_export(self, params: str, ast_node: Node):
        self._exported = True

    # noinspection PyUnusedLocal
    def _parse_class_field(self, params: str, ast_node: Node):
        """
        ---@field [public|protected|private] field_name FIELD_TYPE[|OTHER_TYPE] [@comment]
        """
        # noinspection PyBroadException
        try:
            parts = params.split(' ', 2)  # split visibility and field name

            if len(parts) < 3:
                self._report_error(ast_node, "invalid @field tag: @field %s", params)
                return

            try:
                field_visibility: LuaVisibility = self._parse_visibility(parts[0])
                field_name: str = parts[1]
                field_type_desc: str = parts[2]
            except ValueError:  # no visibility specified
                field_visibility = LuaVisibility.PUBLIC  # default visibility
                field_name: str = parts[0]
                field_type_desc: str = " ".join(parts[1:])

            doc_type, desc = emmylua.parse_param_field(field_type_desc)
            field = LuaClassField(name=field_name,
                                  desc=desc,
                                  lua_type=doc_type,
                                  visibility=field_visibility)

            if self._pending_class:
                self._pending_class[-1].fields.append(field)

            return field
        except Exception as e:
            self._report_error(ast_node, "invalid @field tag: @field %s", params)

    # noinspection PyMethodMayBeStatic
    def _parse_function(self, params: str, ast_node: nodes.Function) -> LuaFunction or LuaClass:
        """ Function name can describe a method or a static method on a class.
            For example: getSpeed, Car:getSpeed, Car.getMaxSpeed
        """
        match = LuaDocParser.FUNCTION_RE.search(params)
        short_desc, long_desc = self._get_short_desc_and_desc()

        if match is None:  # empty function name
            # try to deduce it from ast node
            return LuaFunction(get_lua_function_name(ast_node), short_desc, long_desc)
        if match.group(1):  # function name provided
            name = match.group(1)
            if ":" in name or "." in name:  # method
                parts = re.split('[:.]', name)
                lua_class = LuaClass(parts[0])
                method = LuaFunction(parts[1]).init(ast_node)
                method.is_static = "." in name
                lua_class.methods.append(method)
                self._pending_function.append(method)
                return lua_class
            else:
                return LuaFunction(match.group(1), short_desc, long_desc).init(ast_node)
        else:
            self._report_error(ast_node, "invalid @function tag: @function %s", params)

    # noinspection PyUnusedLocal
    def _parse_private(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].visibility = LuaVisibility.PRIVATE
        else:
            self._pending_qualifiers.append(LuaPrivateQualifier())

    # noinspection PyUnusedLocal
    def _parse_protected(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].visibility = LuaVisibility.PROTECTED
        else:
            self._pending_qualifiers.append(LuaProtectedQualifier())

    def _report_error(self, ast_node: Node, message: str, *args, **kargs):
        report_error(self.file_path, ast_node, message, *args, **kargs)


def report_error(filepath: str, ast_node: Node, message: str, *args, **kwargs) -> None:
    """ Enhance error message by prepending filename and line number"""
    try:
        line_number = get_ast_node_line(ast_node, filepath)
        logging.error(filepath + ": l." + str(line_number) + ": " + message, *args, **kwargs)
    except:
        logging.error(filepath + ": l." + message, *args, **kwargs)


def get_ast_node_line(ast_node: Node, file_path: str):
    """ retrieve the line number of an ast node using char offset """
    file = open(file_path, "r")
    line_number = file.read(ast_node.start_char).count('\n') + 1
    file.close()
    return line_number


def read_index(index: nodes.Index) -> (str, str):
    """
    Get the idx and value part of an nodes.Index as str.
    """
    idx = ""
    value = ""

    if isinstance(index.idx, Name):
        idx = index.idx.id
    elif isinstance(index.idx, String):
        idx = index.idx.s
    if isinstance(index.value, Name):
        value = index.value.id

    return idx, value


def get_lua_function_name(node: Function):
    """
    Retrieve the function name from an ast function node.
    """
    if isinstance(node, Function):
        if isinstance(node.name, Index):
            return read_index(node.name)[0]
        else:
            return node.name.id
    return "unknown"


# noinspection PyPep8Naming
class TreeVisitor:
    def __init__(self, doc_options: DocOptions, file_path: str):
        self._doc_options = doc_options
        self.parser = LuaDocParser(self._doc_options, file_path)
        self.file_path = file_path

        self._class_map = {}
        self._function_list = []
        self._module: Optional[LuaModule] = None
        self._type_handler = {
            LuaClass: self._add_class,
            LuaFunction: self._add_function,
            LuaModule: self._add_module,
            LuaDict: self._add_dict,
            LuaData: self._add_data,
            LuaValue: self._add_data,
        }

    def visit(self, node):
        if node is None:
            return
        if isinstance(node, Node):
            name = 'visit_' + node.__class__.__name__
            visitor = getattr(self, name, None)
            if visitor:
                visitor(node)

        elif isinstance(node, list):
            for n in node:
                self.visit(n)

    def get_model(self) -> LuaModule:
        """ Retrieve the final doc model.
        """
        if self._module:
            model: LuaModule = self._module
        else:
            model: LuaModule = LuaModule('unknown')

        model.file_path = self.file_path

        if model.is_class_mod:
            if len(self._class_map) != 1:
                raise SyntaxException('in a @classmod, only one class is allowed')

            lua_class = self._class_map[list(self._class_map.keys())[0]]
            lua_class.name = model.name
            lua_class.desc = model.desc
            lua_class.usage = model.usage

            model.classes.append(lua_class)
        else:
            # add all classes to module
            model.classes.extend(self._class_map.values())

        model.functions.extend(self._function_list)
        return model

    def _report_error(self, ast_node: Node, message: str, *args, **kargs):
        report_error(self.file_path, ast_node, message, *args, **kargs)

    # ####################################################################### #
    # Sorting and adding custom data from ast into Ldoc Nodes                 #
    # ####################################################################### #
    def _add_class(self, ldoc_node: LuaClass, ast_node):
        # try to extract class name in source in case of assignment
        if isinstance(ast_node, Assign) and len(ast_node.targets) == 1:
            first_target: nodes.Expression = cast(Assign, ast_node).targets[0]
            if isinstance(first_target, nodes.Name):
                ldoc_node.name_in_source = first_target.id
        if ldoc_node.name_in_source == "":
            ldoc_node.name_in_source = ldoc_node.name

        if ldoc_node.name in self._class_map:
            # class already exists, merge it into existing one
            cls: LuaClass = self._class_map[ldoc_node.name_in_source]
            cls.methods.extend(ldoc_node.methods)
            cls.fields.extend(ldoc_node.fields)
            # logging.warning("Overriding class " + ldoc_node.name_in_source)
        else:
            self._class_map[ldoc_node.name_in_source] = ldoc_node

    def _add_function(self, ldoc_node: LuaFunction, ast_node: Function or Assign or Method):
        """ Called when a LuaFunction is added.
            Check if informations must be added directly from source code.
            Add the function in pending list or in a class.
        """
        # check if we need to deduce ldoc_node.name from ast_node
        if not ldoc_node.name:
            if type(ast_node.name) == Name and ast_node.name.id:
                # must be completed by code ?
                if ldoc_node.name == '':
                    ldoc_node.name = ast_node.name.id

        # check consistency
        self._check_function_args(ldoc_node, ast_node)

        if isinstance(ast_node, Method):
            # try to register this function in a class
            class_name = cast(Method, ast_node).source.id

            if class_name in self._class_map:
                self._class_map[class_name].methods.append(ldoc_node)
            else:
                self._function_list.append(ldoc_node)
        # static method
        elif isinstance(ast_node, Function):
            if isinstance(ast_node.name, Index):
                # for now handle only foo.bar syntax
                idx, value = read_index(ast_node.name)

                class_name = value
                func_name = idx
                ldoc_node.name = func_name
                ldoc_node.is_static = True
                if class_name in self._class_map:
                    self._class_map[class_name].methods.append(ldoc_node)
                elif self._module and not self._module.is_class_mod:
                    self._module.functions.append(ldoc_node)

        else:
            self._function_list.append(ldoc_node)

        self._auto_private(ldoc_node)

    def _auto_private(self, func: LuaFunction):
        """
        Set a function as private if it starts with the right prefix.
        """
        if func.name.startswith(self._doc_options.private_prefix):
            func.visibility = LuaVisibility.PRIVATE

    # noinspection PyUnusedLocal
    def _add_module(self, module: LuaModule, ast_node):
        """ Called when a new module is parsed.
            Throw an exception is more than one module is added
        """
        self._check_usage_field(module.usage)

        if not self._module:
            self._module = module
        else:
            raise SyntaxException('only one @module is allowed by file')

    # noinspection PyUnusedLocal
    def _add_dict(self, data: LuaDict, ast_node):
        if self._module:
            self._module.data.append(data)

    # noinspection PyUnusedLocal
    def _add_data(self, data: LuaData, ast_node):
        if self._module:
            self._module.data.append(data)

    def _process_ldoc(self, ast_node):
        """Sort ldoc nodes by type in map"""
        ldoc_nodes, pending_str = self.parser.parse_comments(ast_node)
        for n in ldoc_nodes:
            if type(n) in self._type_handler:
                self._type_handler[type(n)](n, ast_node)
        return ldoc_nodes, pending_str

    # noinspection PyMethodMayBeStatic
    def _auto_param_from_meth_ast(self, doc_node: LuaFunction, ast_node: nodes.Method):
        """
        Automatically create param doc from a Function ast node.
        """
        doc_param_dict: Dict[str, LuaParam] = {p.name: p for p in doc_node.params}

        for arg in ast_node.args:
            if isinstance(arg, nodes.Name):
                if arg.id not in doc_param_dict:
                    doc_node.params.append(LuaParam(name=arg.id, desc=""))
            elif isinstance(arg, nodes.Varargs):
                doc_node.params.append(LuaParam(name="...", desc=""))

    # ####################################################################### #
    # Checking doc consistency                                                #
    # ####################################################################### #
    # noinspection PyMethodMayBeStatic
    def _check_function_args(self, func_doc_node: LuaFunction, func_ast_node: Node):
        if isinstance(func_ast_node, Function):
            # only check if there are too many documented node and consistency
            if len(func_doc_node.params) > len(func_ast_node.args):
                self._report_error(func_ast_node, 'function: "%s": too many documented params: %s', func_doc_node.name,
                                   ', '.join([p.name for p in func_doc_node.params[len(func_ast_node.args):]]))

            args_map = zip(func_doc_node.params, func_ast_node.args)

            for doc, ast_node in args_map:
                if type(ast_node) != Varargs:
                    if doc.name != ast_node.id:
                        self._report_error(func_ast_node, 'function: "%s": doc param found "%s", expected "%s"',
                                           func_doc_node.name, doc.name, ast_node.id)

    # noinspection PyMethodMayBeStatic
    def _check_usage_field(self, usage: str):
        if len(usage) > 0:
            try:
                ast.parse(usage)
            except Exception as e:
                logging.warning("Invalid usage exemple: " + str(e))

    # ####################################################################### #
    # Root Nodes                                                              #
    # ####################################################################### #
    def visit_Chunk(self, node: nodes.Chunk):
        self._process_ldoc(node)
        self.visit(node.body)

    def visit_Block(self, node):
        self.visit(node.body)

    def visit_Node(self, node):
        pass

    # ####################################################################### #
    # Assignments                                                             #
    # ####################################################################### #
    def visit_Assign(self, node):
        self._process_ldoc(node)
        self.visit(node.targets)
        self.visit(node.values)

    def visit_LocalAssign(self, node):
        self._process_ldoc(node)
        self.visit(node.targets)
        self.visit(node.values)

    # ####################################################################### #
    # Control Structures                                                      #
    # ####################################################################### #
    def visit_While(self, node):
        self.visit(node.test)
        self.visit(node.body)

    def visit_Do(self, node):
        self.visit(node.body)

    def visit_Repeat(self, node):
        self.visit(node.body)
        self.visit(node.test)

    def visit_Forin(self, node):
        self.visit(node.iter)
        self.visit(node.targets)
        self.visit(node.body)

    def visit_Fornum(self, node):
        self.visit(node.target)
        self.visit(node.start)
        self.visit(node.stop)
        self.visit(node.step)
        self.visit(node.body)

    def visit_If(self, node):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_ElseIf(self, node):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    # ####################################################################### #
    # Call / Invoke / Method / Anonymous                                      #
    # ####################################################################### #
    def visit_Function(self, node: Function):
        doc_nodes, pending_str = self._process_ldoc(node)

        for doc_node in doc_nodes:
            if isinstance(doc_node, LuaFunction):
                # check if it's a static method: foo.bar()
                if isinstance(node.name, Index):
                    # for now handle only foo.bar syntax
                    if isinstance(node.name.idx, Name) and isinstance(node.name.value, Name):
                        potential_cls_name: str = node.name.value.id
                        # auto-create class doc model
                        if potential_cls_name not in self._class_map and self._function_list:
                            self._class_map[potential_cls_name] = LuaClass(potential_cls_name)
                            func_model = self._function_list.pop()
                            self._check_function_args(func_model, node)
                            self._class_map[potential_cls_name].methods.append(func_model)

        self.visit(node.args)
        self.visit(node.body)

    def visit_LocalFunction(self, node: LocalFunction):
        self._process_ldoc(node)
        self.visit(node.args)
        self.visit(node.body)

    def visit_Method(self, node: Method):
        doc_nodes, pending_str = self._process_ldoc(node)

        if type(node.source) == Name and type(node.name) == Name:
            # auto-create class doc model
            if node.source.id not in self._class_map:
                self._class_map[node.source.id] = LuaClass(node.source.id)
                if doc_nodes:
                    func_model = self._function_list.pop()
                    self._check_function_args(func_model, node)
                    self._class_map[node.source.id].methods.append(func_model)
                logging.debug('created %s class', node.source.id)

            # auto-create method doc model
            if not doc_nodes:
                short_desc = ''
                desc = ''

                if len(pending_str) > 0:
                    short_desc = pending_str[0]
                if len(pending_str) > 1:
                    desc = ' '.join(pending_str[1:])

                func_model = LuaFunction(node.name.id, short_desc, desc, []).init(node)
                self._auto_param_from_meth_ast(func_model, node)
                self._check_function_args(func_model, node)

                if node.source.id in self._class_map:
                    self._class_map[node.source.id].methods.append(func_model)

        self.visit(node.source)
        self.visit(node.args)
        self.visit(node.body)

    def visit_AnonymousFunction(self, node):
        self.visit(node.args)
        self.visit(node.body)

    def visit_Index(self, node):
        self.visit(node.value)
        self.visit(node.idx)

    def visit_Call(self, node):
        self._process_ldoc(node)
        self.visit(node.func)
        self.visit(node.args)

    def visit_Invoke(self, node):
        self.visit(node.source)
        self.visit(node.func)
        self.visit(node.args)

    # ####################################################################### #
    # Operators                                                               #
    # ####################################################################### #
    def visit_BinaryOp(self, node):
        self.visit(node.left)
        self.visit(node.right)

    # ####################################################################### #
    # Types and Values                                                        #
    # ####################################################################### #
    def visit_Table(self, node: nodes.Table):
        self.visit(node.fields)

    def visit_Field(self, node: nodes.Field):
        self._process_ldoc(node)
        self.visit(node.key)
        self.visit(node.value)

    def visit_Return(self, node):
        self.visit(node.values)


class DocParser:
    def __init__(self, doc_options: DocOptions = DocOptions()):
        self._doc_options = doc_options

    def build_module_doc_model(self, input_src: str, file_path: str) -> LuaModule:
        # try to get AST tree, do nothing if invalid source code is provided
        try:
            tree = ast.parse(input_src)
        except Exception as e:
            logging.error(str(e))
            raise

        visitor = TreeVisitor(self._doc_options, file_path)
        visitor.visit(tree)
        return visitor.get_model()
