import logging
import re
from luaparser import ast
from luaparser.astnodes import *
import luaparser.astnodes as nodes
from luadoc.model import *
from typing import List, Dict, cast, Callable
import luadoc.emmylua as emmylua


class DocOptions:
    def __init__(self):
        self.comment_prefix = '---'
        self.emmy_lua_syntax = True
        self.private_prefix = "_"


class SyntaxException(Exception):
    pass


class LuaDocParser:
    """ Lua doc style parser
    """

    FUNCTION_RE = re.compile(r'^(\w+)')
    DOC_CLASS_RE = re.compile(r'^([\w\.]+)(?: *: *([\w\.]+))?')
    PARAM_RE = re.compile(r'^(\w+) *([\w+|]+) *(.*)')

    def __init__(self, options: DocOptions):
        self._start_symbol: str = options.comment_prefix
        # list of string with no tag
        self._pending_str: List[str] = []
        self._pending_param: List[LuaParam] = []
        self._pending_return: List[LuaReturn] = []
        self._pending_function: List[LuaFunction] = []
        self._pending_qualifiers: List[LuaQualifier] = []  # @virtual, @abstract, @deprecated
        self._pending_class: List[LuaClass] = []
        self._pending_module: List[LuaModule] = []
        self._pending_overload: List[LuaTypeCallable] = []
        self._usage_in_progress: bool = False
        self._usage_str: List[str] = []

        # install handlers
        self._handlers: Dict[str, Callable[[str, Node], LuaNode or None]] = {
            '@abstract': self._parse_abstract,
            '@class': self._parse_class,
            '@classmod': self._parse_class_mod,
            '@deprecated': self._parse_deprecated,
            '@field': self._parse_class_field,
            '@function': self._parse_function,
            '@int': self._parse_int_param,
            '@module': self._parse_module,
            '@overload': self._parse_overload,
            '@param': self._parse_emmy_lua_param if options.emmy_lua_syntax else self._parse_param,
            '@private': self._parse_private,
            '@protected': self._parse_protected,
            '@return': self._parse_emmy_lua_return if options.emmy_lua_syntax else self._parse_return,
            '@string': self._parse_string_param,
            '@tparam': self._parse_tparam,
            '@tparam[opt]': self._parse_tparam_opt,
            '@treturn': self._parse_treturn,
            '@type': self._parse_class,
            '@usage': self._parse_usage,
            '@virtual': self._parse_virtual,
            "@vararg": self._parse_varargs,
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

        nodes: List[LuaNode] = []
        for comment in comments:
            node = self._parse_comment(comment, ast_node)
            if node is not None:
                nodes.append(node)

        # handle pending nodes
        if self._pending_param or self._pending_return or self._pending_qualifiers:
            # methods
            if type(ast_node) == Method:
                if self._pending_str:
                    short_desc = self._pending_str.pop(0)
                else:
                    short_desc = ''
                long_desc = '\n'.join(self._pending_str)
                nodes.append(LuaFunction('', short_desc, long_desc, [], self._pending_return))

            # Detect static method: a Function with an Index as name
            if type(ast_node) == Function:
                if self._pending_str:
                    short_desc = self._pending_str.pop(0)
                else:
                    short_desc = ''
                long_desc = '\n'.join(self._pending_str)
                nodes.append(LuaFunction('', short_desc, long_desc, [], self._pending_return))

        # handle function pending elements
        if nodes and type(nodes[-1]) is LuaFunction:
            func: LuaFunction = cast(LuaFunction, nodes[-1])

            # handle pending qualifiers
            if self._pending_qualifiers:
                for qualifier in self._pending_qualifiers:
                    if type(qualifier) is LuaVirtualQualifier:
                        cast(LuaVirtualQualifier, nodes[-1]).is_virtual = True
                    elif type(qualifier) is LuaAbstractQualifier:
                        cast(LuaAbstractQualifier, nodes[-1]).is_abstract = True
                    elif type(qualifier) is LuaDeprecatedQualifier:
                        cast(LuaDeprecatedQualifier, nodes[-1]).is_deprecated = True
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
                nodes.append(self._create_function_overload(func, overload))

        # handle module pending elements
        if self._pending_module:
            if self._usage_str:
                self._pending_module[-1].usage = '\n'.join(self._usage_str)

        return nodes, self._pending_str

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
                        return self._handlers[parts[0]](parts[1] if len(parts) > 1 else "", ast_node)
                elif not self._usage_in_progress:
                    # its just a string
                    self._pending_str.append(text)
                else:
                    self._usage_str.append(comment[len(self._start_symbol) + 1:])
        return None

    def _parse_class(self, params: str, ast_node: Node):
        """
        --@class MY_TYPE[:PARENT_TYPE] [@comment]
        """
        match = LuaDocParser.DOC_CLASS_RE.search(params)
        main_class = LuaClass(match.group(1), match.group(1))

        if match.group(2):  # has base class
            main_class.inherits_from.append(match.group(2))

        self._pending_class.append(main_class)

        return main_class

    # noinspection PyUnusedLocal
    def _parse_usage(self, params: str, ast_node: Node):
        """
        usage must be valid lua source code
        """
        self._usage_in_progress = True

    # noinspection PyUnusedLocal
    def _parse_module(self, params: str, ast_node: Node):
        return LuaModule(params)

    # noinspection PyUnusedLocal
    def _parse_overload(self, params: str, ast_node: Node):
        try:
            model, desc = emmylua.parse_param_field(params)
            self._pending_overload.append(model)
        except Exception:
            raise SyntaxException('invalid @overload field: ' + params)

    # noinspection PyUnusedLocal
    def _parse_class_mod(self, params: str, ast_node: Node) -> LuaModule:
        module = LuaModule(params)
        module.isClassMod = True
        module.desc = '\n'.join(self._pending_str)

        if self._usage_in_progress:
            module.usage = '\n'.join(self._usage_str)
            self._usage_in_progress = False

        self._pending_module.append(module)

        return module

    def _parse_type(self, type_str: str):
        if type_str in self._param_type_str_to_lua_types:
            return LuaType(self._param_type_str_to_lua_types[type_str])
        return LuaType(LuaTypes.CUSTOM, type_str)

    def _parse_visibility(self, string: str):
        if string in LuaVisibility_from_str:
            return LuaVisibility_from_str[string]
        else:
            raise SyntaxException("Invalid visibility string: " + string)

    def _parse_tparam(self, params: str, astnode: Node, is_opt: bool = False):
        parts = params.split()

        if len(parts) > 2:
            lua_type = self._parse_type(parts[0])
            name = parts[1]
            desc = ' '.join(parts[2:])

            param = LuaParam(name, desc, lua_type, is_opt)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            raise SyntaxException('@tparam expect two parameters')

    # noinspection PyUnusedLocal
    def _parse_tparam_opt(self, params: str, ast_node: Node):
        self._parse_tparam(params, ast_node, True)

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
            raise SyntaxException('@param expect one parameters')

    # noinspection PyUnusedLocal
    def _parse_emmy_lua_param(self, params: str, ast_node: Node):
        """
        param_name MY_TYPE[|other_type] [@comment]
        """
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
            raise SyntaxException('invalid @param field: ' + params)

    def _parse_string_param(self, params: str):
        self._parse_tparam("string " + params)

    def _parse_int_param(self, params: str):
        self._parse_tparam("int " + params)

    # noinspection PyUnusedLocal
    def _parse_treturn(self, params: str, ast_node: Node):
        parts = params.split()

        if len(parts) >= 2:
            lua_type = self._parse_type(parts[0])
            desc = ' '.join(parts[1:])

            param = LuaReturn(desc, lua_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            raise SyntaxException('@treturn expect at least two parameters (%s)' % str(params))

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
            raise SyntaxException('@return expect one parameter')

    # noinspection PyUnusedLocal
    def _parse_emmy_lua_return(self, params: str, ast_node: Node):
        try:
            doc_type, desc = emmylua.parse_param_field(params)
            lua_return = LuaReturn(desc, doc_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(lua_return)
            else:
                self._pending_return.append(lua_return)
        except Exception:
            raise SyntaxException('invalid @return field: ' + params)

    # noinspection PyUnusedLocal
    def _parse_virtual(self, params: str, ast_node: Node):
        if self._pending_function:
            self._pending_function[-1].is_virtual = True
        else:
            self._pending_qualifiers.append(LuaVirtualQualifier())

    # noinspection PyUnusedLocal
    def _parse_varargs(self, params: str, ast_node: Node):
        try:
            doc_type, desc = emmylua.parse_param_field(params)
            param = LuaParam("...", desc, doc_type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        except Exception:
            raise SyntaxException('invalid @param field: ' + params)

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
    def _parse_class_field(self, params: str, ast_node: Node):
        """
        ---@field [public|protected|private] field_name FIELD_TYPE[|OTHER_TYPE] [@comment]
        """
        try:
            parts = params.split(' ', 2)  # split visibility and field name

            if len(parts) < 3:
                raise SyntaxException("@field expect at least a visibility, a name and a type")

            field_visibility: LuaVisibility = self._parse_visibility(parts[0])
            field_name: str = parts[1]
            field_type_desc: str = parts[2]
            doc_type, desc = emmylua.parse_param_field(field_type_desc)
            field = LuaClassField(name=field_name,
                                  desc=desc,
                                  lua_type=doc_type,
                                  visibility=field_visibility)

            if self._pending_class:
                self._pending_class[-1].fields.append(field)

            return field
        except Exception:
            raise SyntaxException('invalid @field tag')

    def _parse_function(self, params: str, ast_node: Node) -> LuaFunction:
        match = LuaDocParser.DOC_CLASS_RE.search(params)

        if match is None:  # empty function name
            # try to deduce it from ast node
            return LuaFunction(get_lua_function_name(ast_node))
        if match.group(1):  # function name provided
            return LuaFunction(match.group(1))
        else:
            raise SyntaxException('@function invalid statement')

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

def get_lua_function_name(node: Node):
    """
    Retrieve the function name from an ast function node.
    """
    if isinstance(node, Function):
        if isinstance(node.name, Index):
            return node.name.idx.id
        else:
            return node.name.id
    return "unknown"


class TreeVisitor:
    def __init__(self, doc_options: DocOptions):
        self._doc_options = doc_options
        self.parser = LuaDocParser(self._doc_options)

        self._class_map = {}
        self._function_list = []
        self._module: LuaModule = None
        self._type_handler = {
            LuaClass: self._add_class,
            LuaFunction: self._add_function,
            LuaModule: self._add_module,
        }

    def visit(self, node):
        if node is None:
            return
        if isinstance(node, Node):
            # call enter node method
            # if no visitor method found for this arg type,
            # search in parent arg type:
            parent_type = node.__class__
            while parent_type != object:
                name = 'visit_' + parent_type.__name__
                visitor = getattr(self, name, None)
                if visitor:
                    visitor(node)
                    break
                else:
                    parent_type = parent_type.__bases__[0]

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

        if model.isClassMod:
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

    # ####################################################################### #
    # Sorting and adding custom data from ast into Ldoc Nodes                 #
    # ####################################################################### #
    def _add_class(self, ldoc_node, ast_node):
        # try to extract class name in source in case of assignment
        if isinstance(ast_node, Assign) and len(ast_node.targets) == 1:
            if type(ast_node.targets[0]) == Name:
                ldoc_node.name_in_source = ast_node.targets[0].id

        self._class_map[ldoc_node.name_in_source] = ldoc_node

    def _add_function(self, ldoc_node: LuaFunction, ast_node: Function or Assign):
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
            class_name = ast_node.source.id

            if class_name in self._class_map:
                self._class_map[class_name].methods.append(ldoc_node)
            else:
                self._function_list.append(ldoc_node)
        # static method
        elif isinstance(ast_node, Function):
            if isinstance(ast_node.name, Index):
                # for now handle only foo.bar syntax
                if isinstance(ast_node.name.idx, Name) and isinstance(ast_node.name.value, Name):
                    class_name = ast_node.name.value.id
                    func_name = ast_node.name.idx.id

                    ldoc_node.name = func_name
                    ldoc_node.is_static = True
                    if class_name in self._class_map:
                        self._class_map[class_name].methods.append(ldoc_node)
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

    def _process_ldoc(self, ast_node):
        """Sort ldoc nodes by type in map"""
        ldoc_nodes, pending_str = self.parser.parse_comments(ast_node)
        for n in ldoc_nodes:
            if type(n) in self._type_handler:
                self._type_handler[type(n)](n, ast_node)
        return ldoc_nodes, pending_str

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
    def _check_function_args(self, func_doc_node: LuaFunction, func_ast_node: Node):
        if isinstance(func_ast_node, Function):
            # only check if there are too many documented node and consistency
            if len(func_doc_node.params) > len(func_ast_node.args):
                raise SyntaxException('function: "%s": too many documented params: %s'
                                      % (func_doc_node.name,
                                         ', '.join([p.name for p in func_doc_node.params[len(func_ast_node.args):]])))

            args_map = zip(func_doc_node.params, func_ast_node.args)

            for doc, ast in args_map:
                if type(ast) != Varargs:
                    if doc.name != ast.id:
                        raise SyntaxException('function: "%s": doc param found "%s", expected "%s"'
                                              % (func_doc_node.name, doc.name, ast.id))

    def _check_usage_field(self, usage: str):
        if len(usage) > 0:
            try:
                ast.parse(usage)
            except Exception as e:
                logging.warning("Invalid usage exemple: " + str(e))

    # ####################################################################### #
    # Root Nodes                                                              #
    # ####################################################################### #
    def visit_Chunk(self, node):
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
                        potential_cls_name = node.name.value.id
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

                func_model = LuaFunction(node.name.id, short_desc, desc, [])
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
    def visit_Table(self, node):
        self.visit(node.fields)

    def visit_Field(self, node):
        self.visit(node.key)
        self.visit(node.value)

    def visit_Return(self, node):
        self.visit(node.values)


class DocParser:
    def __init__(self, doc_options: DocOptions = DocOptions()):
        self._doc_options = doc_options

    def build_module_doc_model(self, input_src: str) -> LuaModule:
        # try to get AST tree, do nothing if invalid source code is provided
        try:
            tree = ast.parse(input_src)
        except Exception as e:
            logging.error(str(e))
            raise

        visitor = TreeVisitor(self._doc_options)
        visitor.visit(tree)
        return visitor.get_model()
