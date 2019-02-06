"""
Handle the @export tag.

It use Lua AST to create doc automatically.
"""
from luadoc.model import *
import luaparser.astnodes as nodes


def parse_export(node: nodes.Node):
    visitor: ExportVisitor = ExportVisitor()
    ret = visitor.visit(node)
    return ret

def join_comments(node: nodes.Node):
    return "\n".join([c.s.strip(" -") for c in node.comments])


class ExportVisitor:
    def __init__(self):
        self._processed: List[LuaDict] = []
        self._data_stack: List[LuaDict] = []

    # ####################################################################### #
    # Root Nodes                                                              #
    # ####################################################################### #
    def visit_Chunk(self, node: nodes.Chunk):
        self.visit(node.body)

    def visit_Block(self, node: nodes.Block):
        self.visit(node.body)

    # ####################################################################### #
    # Assignments                                                             #
    # ####################################################################### #
    def visit_Assign(self, node: nodes.Assign):
        self.visit(node.targets)
        self.visit(node.values)

    def visit_LocalAssign(self, node: nodes.LocalAssign):
        self.visit(node.targets)
        return self.visit(node.values)

    # ####################################################################### #
    # Control Structures                                                      #
    # ####################################################################### #
    def visit_While(self, node: nodes.While):
        self.visit(node.test)
        self.visit(node.body)

    def visit_Do(self, node: nodes.Do):
        self.visit(node.body)

    def visit_Repeat(self, node: nodes.Repeat):
        self.visit(node.body)
        self.visit(node.test)

    def visit_Forin(self, node: nodes.Forin):
        self.visit(node.iter)
        self.visit(node.targets)
        self.visit(node.body)

    def visit_Fornum(self, node: nodes.Fornum):
        self.visit(node.target)
        self.visit(node.start)
        self.visit(node.stop)
        self.visit(node.step)
        self.visit(node.body)

    def visit_If(self, node: nodes.If):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_ElseIf(self, node: nodes.ElseIf):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    # ####################################################################### #
    # Call / Invoke / Method / Anonymous                                      #
    # ####################################################################### #
    def visit_Function(self, node: nodes.Function):
        self.visit(node.args)
        self.visit(node.body)

    def visit_LocalFunction(self, node: nodes.LocalFunction):
        self.visit(node.args)
        self.visit(node.body)

    def visit_Method(self, node: nodes.Method):
        self.visit(node.source)
        self.visit(node.args)
        self.visit(node.body)

    def visit_AnonymousFunction(self, node: nodes.AnonymousFunction):
        self.visit(node.args)
        self.visit(node.body)

    def visit_Index(self, node: nodes.Index):
        self.visit(node.value)
        self.visit(node.idx)

    def visit_Call(self, node: nodes.Call):
        self.visit(node.func)
        self.visit(node.args)

    def visit_Invoke(self, node: nodes.Invoke):
        self.visit(node.source)
        self.visit(node.func)
        self.visit(node.args)

    # ####################################################################### #
    # Operators                                                               #
    # ####################################################################### #
    def visit_BinaryOp(self, node: nodes.BinaryOp):
        self.visit(node.left)
        self.visit(node.right)

    # ####################################################################### #
    # Types and Values                                                        #
    # ####################################################################### #
    def visit_Table(self, node: nodes.Table):
        self._data_stack.append(LuaDict("", ""))
        self.visit(node.fields)
        return self._data_stack.pop()

    def visit_Field(self, node: nodes.Field):
        field_name = node.key.id
        field_desc = join_comments(node)
        doc_field = LuaDictField(field_name, field_desc)
        self._data_stack[-1].fields.append(doc_field)

        key = self.visit(node.key)
        value = self.visit(node.value)

        if value:
            doc_field.desc = value


    def visit_Return(self, node: nodes.Return):
        self.visit(node.values)

    def visit(self, node):
        if node is None:
            return
        if isinstance(node, nodes.Node):
            name = 'visit_' + node.__class__.__name__
            visitor = getattr(self, name, None)
            if visitor:
                return visitor(node)

        elif isinstance(node, list):
            return [self.visit(n) for n in node]
