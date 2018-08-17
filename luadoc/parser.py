import logging
from luaparser import ast
from luaparser.astnodes import *
from luadoc.model import *
from typing import List


class DocOptions:
    def __init__(self):
        self.comment_prefix = '---'


class SyntaxException(Exception):
    pass


class LuaDocParser:
    """ Lua doc style parser
    """
    def __init__(self, start_symbol: str):
        self._start_symbol = start_symbol
        # list of string with no tag
        self._pending_str = []
        self._pending_param = []
        self._pending_return = []
        self._pending_function = []
        self._pending_qualifiers = []  # @virtual, @abstract, @deprecated
        self._usage_in_progress = False
        self._usage_str = []
        self._handlers = {
            '@abstract': self._parse_abstract,
            '@class': self._parse_class,
            '@classmod': self._parse_class_mod,
            '@deprecated': self._parse_deprecated,
            '@int': self._parse_int_param,
            '@module': self._parse_module,
            '@param': self._parse_param,
            '@private': self._parse_private,
            '@return': self._parse_return,
            '@string': self._parse_string_param,
            '@tparam': self._parse_tparam,
            '@tparam[opt]': self._parse_tparam_opt,
            '@treturn': self._parse_treturn,
            '@type': self._parse_class,
            '@usage': self._parse_usage,
            '@virtual': self._parse_virtual,
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

    def parse_comments(self, ast_node):
        comments = [c.s for c in ast_node.comments]

        # reset pending list
        self._pending_str = []
        self._pending_param = []
        self._pending_function = []
        self._pending_return = []
        self._pending_qualifiers = []
        self._usage_in_progress = False
        self._usage_str = []

        nodes = []
        for comment in comments:
            node = self._parse_comment(comment)
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
                nodes.append(LuaFunction('', short_desc, long_desc, self._pending_param, self._pending_return))

        # handle function pending elements
        if nodes and type(nodes[-1]) is LuaFunction:
            # handle pending qualifiers
            if self._pending_qualifiers:
                for qualifier in self._pending_qualifiers:
                    if type(qualifier) is LuaVirtualQualifier:
                        nodes[-1].is_virtual = True
                    elif type(qualifier) is LuaAbstractQualifier:
                        nodes[-1].is_abstract = True
                    elif type(qualifier) is LuaDeprecatedQualifier:
                        nodes[-1].is_deprecated = True
                    else:
                        nodes[-1].visibility = LuaVisibility.PRIVATE

            # handle pending usage
            if self._usage_in_progress:
                nodes[-1].usage = '\n'.join(self._usage_str)

        return nodes, self._pending_str

    def _parse_comment(self, comment:str):
        parts = comment.split()
        if parts:
            if parts[0].startswith(self._start_symbol):
                if len(parts) > 1 and parts[1].startswith('@'):
                    if parts[1] in self._handlers:
                        return self._handlers[parts[1]](parts[2:])
                elif not self._usage_in_progress:
                    # its just a string
                    self._pending_str.append(' '.join(parts[1:]))
                else:
                    self._usage_str.append(comment[len(self._start_symbol)+1:])
        return None

    def _parse_class(self, params:List[str]):
        if len(params) > 0:
            return LuaClass(params[0], params[0])
        else:
            raise SyntaxException('@class must be followed by a class name')

    def _parse_usage(self, params:List[str]):
        self._usage_in_progress = True

    def _parse_module(self, params:List[str]):
        if len(params) > 0:
            return LuaModule(params[0])
        else:
            raise SyntaxException('@module must be followed by a module name')

    def _parse_class_mod(self, params:List[str]):
        if len(params) > 0:
            module = LuaModule(params[0])
            module.isClassMod = True
            module.desc = '\n'.join(self._pending_str)

            if self._usage_in_progress:
                module.usage = '\n'.join(self._usage_str)
                self._usage_in_progress = False

            return module
        else:
            raise SyntaxException('@classmod must be followed by a module name')

    def _parse_type(self, type_str:str):
        if type_str in self._param_type_str_to_lua_types:
            return LuaType(self._param_type_str_to_lua_types[type_str])
        return LuaType(LuaTypes.CUSTOM, type_str)

    def _parse_tparam(self, params:List[str], is_opt:bool=False):
        if len(params) > 2:
            type = self._parse_type(params[0])
            name = params[1]
            desc = ' '.join(params[2:])

            param = LuaParam(name, desc, type, is_opt)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            raise SyntaxException('@tparam expect two parameters')

    def _parse_tparam_opt(self, params:List[str]):
        self._parse_tparam(params, True)

    def _parse_param(self, params:List[str]):
        if len(params) > 1:
            param = LuaParam(params[0], ' '.join(params[1:]))
            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            raise SyntaxException('@param expect one parameters')

    def _parse_string_param(self, params:List[str]):
        params.insert(0, 'string')
        self._parse_tparam(params)

    def _parse_int_param(self, params:List[str]):
        params.insert(0, 'int')
        self._parse_tparam(params)

    def _parse_treturn(self, params:List[str]):
        if len(params) >= 2:
            type = self._parse_type(params[0])
            desc = ' '.join(params[1:])

            param = LuaReturn(desc, type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            raise SyntaxException('@treturn expect at least two parameters (%s)' % str(params))

    def _parse_return(self, params:List[str]):
        if len(params) > 1:
            desc = ' '.join(params[0:])

            param = LuaReturn(desc)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            raise SyntaxException('@treturn expect one parameter')

    def _parse_virtual(self, params:List[str]):
        if self._pending_function:
            self._pending_function[-1].is_virtual = True
        else:
            self._pending_qualifiers.append(LuaVirtualQualifier())

    def _parse_abstract(self, params:List[str]):
        if self._pending_function:
            self._pending_function[-1].is_abstract = True
        else:
            self._pending_qualifiers.append(LuaAbstractQualifier())

    def _parse_deprecated(self, params:List[str]):
        if self._pending_function:
            self._pending_function[-1].is_deprecated = True
        else:
            self._pending_qualifiers.append(LuaDeprecatedQualifier())

    def _parse_private(self, params:List[str]):
        if self._pending_function:
            self._pending_function[-1].visibility = LuaVisibility.PRIVATE
        else:
            self._pending_qualifiers.append(LuaPrivateQualifier())


class TreeVisitor:
    def __init__(self, doc_options):
        self._doc_options = doc_options
        self.parser = LuaDocParser(self._doc_options.comment_prefix)

        self._class_map = {}
        self._function_list = []
        self._module = None
        self._type_handler = {
            LuaClass: self._add_class,
            LuaFunction: self._add_function,
            LuaModule: self._add_module,
        }

    def visit(self, node):
        if node is None: return
        if isinstance(node, Node):
            # call enter node method
            # if no visitor method found for this arg type,
            # search in parent arg type:
            parentType = node.__class__
            while parentType != object:
                name = 'visit_' + parentType.__name__
                visitor = getattr(self, name, None)
                if visitor:
                    visitor(node)
                    break
                else:
                    parentType = parentType.__bases__[0]

        elif isinstance(node, list):
            for n in node:
                self.visit(n)

    def get_model(self):
        """ Retrieve the final doc model.
        """
        if self._module:
            model = self._module
        else:
            model = LuaModule('unknown')

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

    def _add_function(self, ldoc_node, ast_node):
        """ Called when a LuaFunction is added.
            Check if informations must be added directly from source code.
            Add the function in pending list or in a class.
        """
        # check if we need to add infos
        if type(ast_node.name) == Name and ast_node.name.id:
            # must be completed by code ?
            if ldoc_node.name == '':
                ldoc_node.name = ast_node.name.id

        # check consistency
        self._check_function_args(ldoc_node, ast_node)

        # try to register this function in a class
        class_name = ast_node.source.id

        if class_name in self._class_map:
            self._class_map[class_name].methods.append(ldoc_node)
        else:
            self._function_list.append(ldoc_node)

    def _add_module(self, module, ast_node):
        """ Called when a new module is parsed.
            Throw an exception is more than one module is added
        """
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

    # ####################################################################### #
    # Checking doc consistency                                                #
    # ####################################################################### #
    def _check_function_args(self, func_doc_node, func_ast_node):
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

        pass

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
    def visit_Function(self, node):
        self.visit(node.args)
        self.visit(node.body)

    def visit_LocalFunction(self, node):
        self.visit(node.args)
        self.visit(node.body)

    def visit_Method(self, node):
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
                params = []

                if len(pending_str) > 0:
                    short_desc = pending_str[0]
                if len(pending_str) > 1:
                    desc = ' '.join(pending_str[1:])

                func_model = LuaFunction(node.name.id, short_desc, desc, params)
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
    def __init__(self, doc_options):
        self._doc_options = doc_options

    def build_module_doc_model(self, input):
        # try to get AST tree, do nothing if invalid source code is provided
        try:
            tree = ast.parse(input)
        except ast.SyntaxException as e:
            logging.error(str(e))
            return input

        visitor = TreeVisitor(self._doc_options)
        visitor.visit(tree)
        return visitor.get_model()

