import logging
from luaparser import ast
from luaparser.astnodes import *
from luadoc.model import *
from typing import List


class SyntaxException(Exception):
    pass


class LuaDocParser:
    """ Lua doc style parser
    """
    def __init__(self, start_symbol: str='---'):
        self._start_symbol = start_symbol
        # list of string with no tag
        self._pending_str = []
        self._pending_param = []
        self._pending_return = []
        self._pending_function = []
        self._handlers = {
            '@module': self._parse_module,
            '@class': self._parse_class,
            '@classmod': self._parse_class_mod,
            '@tparam': self._parse_tparam,
            '@param': self._parse_param,
            '@treturn': self._parse_treturn,
            '@return': self._parse_return,
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

        nodes = []
        for comment in comments:
            node = self._parse_comment(comment)
            if node is not None:
                nodes.append(node)

        # handle pending nodes
        if self._pending_param or self._pending_return:
            # methods
            if type(ast_node) == Method:
                short_desc = self._pending_str.pop(0)
                long_desc = '\n'.join(self._pending_str)
                nodes.append(LuaFunction('', short_desc, long_desc, self._pending_param, self._pending_return))

        return nodes

    def _parse_comment(self, comment:str):
        parts = comment.split()
        if len(parts) > 1:
            if parts[0] == self._start_symbol:
                if parts[1].startswith('@'):
                    if parts[1] in self._handlers:
                        return self._handlers[parts[1]](parts[2:])
                else:
                    # its just a string
                    self._pending_str.append(' '.join(parts[1:]))
        return None

    def _parse_class(self, params:List[str]):
        if len(params) > 0:
            return LuaClass(params[0], params[0])
        else:
            raise SyntaxException('@class must be followed by a class name')

    def _parse_module(self, params:List[str]):
        if len(params) > 0:
            return LuaModule(params[0])
        else:
            raise SyntaxException('@module must be followed by a module name')

    def _parse_class_mod(self, params:List[str]):
        if len(params) > 0:
            module = LuaModule(params[0])
            module.isClassMod = True
            return module
        else:
            raise SyntaxException('@classmod must be followed by a module name')

    def _parse_type(self, type_str:str):
        if type_str in self._param_type_str_to_lua_types:
            return LuaType(self._param_type_str_to_lua_types[type_str])
        return LuaType(LuaTypes.CUSTOM, type_str)

    def _parse_tparam(self, params:List[str]):
        if len(params) > 2:
            type = self._parse_type(params[0])
            name = params[1]
            desc = ' '.join(params[2:])

            param = LuaParam(name, desc, type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].params.append(param)
            else:
                self._pending_param.append(param)
        else:
            raise SyntaxException('@tparam expect two parameters')

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

    def _parse_treturn(self, params:List[str]):
        if len(params) > 2:
            type = self._parse_type(params[0])
            name = params[1]
            desc = ' '.join(params[2:])

            param = LuaReturn(name, desc, type)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            raise SyntaxException('@treturn expect two parameters')

    def _parse_return(self, params:List[str]):
        if len(params) > 1:
            name = params[0]
            desc = ' '.join(params[1:])

            param = LuaReturn(name, desc)

            # if function pending, add param to it
            if self._pending_function:
                self._pending_function[-1].returns.append(param)
            else:
                self._pending_return.append(param)
        else:
            raise SyntaxException('@treturn expect one parameter')


class TreeVisitor:
    def __init__(self, options):
        self.parser = LuaDocParser()

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

    def getModel(self):
        """ Retrieve the final doc model.
        """
        if self._module:
            model = self._module
        else:
            model = LuaModule('unknown')

        model.statements.extend([v for k, v in self._class_map.items()])
        model.statements.extend(self._function_list)
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
        ldoc_nodes = self.parser.parse_comments(ast_node)
        for n in ldoc_nodes:
            if type(n) in self._type_handler:
                self._type_handler[type(n)](n, ast_node)
        return ldoc_nodes

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
        doc_nodes = self._process_ldoc(node)

        if type(node.source) == Name and type(node.name) == Name:
            if node.source.id not in self._class_map:
                self._class_map[node.source.id] = LuaClass(node.name.id)
                logging.debug('created %s class', node.source.id)

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
        #if type(node.func) == Name and node.func.id == 'class':
        #    self._class_map[self._last_local_assign] = LuaClass(self._last_local_assign)
        #    logging.debug('created %s class', self._last_local_assign)

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

        visitor = TreeVisitor(None)
        visitor.visit(tree)
        return visitor.getModel()

