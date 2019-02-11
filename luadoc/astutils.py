from luaparser.astnodes import *


class IdentifierVisitor:
    def __init__(self):
        self.identifier = ""

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

    def visit_Chunk(self, node: Chunk):
        self.visit(node.body)

    def visit_Block(self, node):
        self.visit(node.body)

    def visit_Node(self, node):
        pass

    def visit_Assign(self, node):
        self.visit(node.targets)
        # self.visit(node.values)

    def visit_LocalAssign(self, node):
        self.visit(node.targets)
        # self.visit(node.values)

    def visit_Function(self, node: Function):
        self.visit(node.args)
        self.visit(node.body)

    def visit_LocalFunction(self, node: LocalFunction):
        self.visit(node.args)
        self.visit(node.body)

    def visit_Method(self, node: Method):
        self.visit(node.source)
        self.visit(node.args)
        self.visit(node.body)

    def visit_Index(self, node):
        self.visit(node.value)
        self.visit(node.idx)

    def visit_Name(self, node: Name):
        self.identifier = node.id

    def visit_String(self, node: String):
        self.identifier = node.s

    def visit_Table(self, node):
        self.visit(node.fields)

    def visit_Field(self, node: Field):
        self.visit(node.key)
        self.visit(node.value)

    def visit_Return(self, node):
        self.visit(node.values)


def get_identifier(node: Node) -> str:
    """ Retrieve identifier if applicable.
        Example:
        local foo.bar = 42
        return "bar"
    """
    visitor = IdentifierVisitor()
    visitor.visit(node)
    return visitor.identifier
