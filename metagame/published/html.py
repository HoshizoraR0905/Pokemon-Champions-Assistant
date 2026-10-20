"""Minimal read-only DOM for the two audited server-rendered team pages."""
from html.parser import HTMLParser

VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
    def text(self):
        return ''.join(c if isinstance(c,str) else c.text() for c in self.children)
    def find(self, tag=None, **attrs):
        for c in self.children:
            if isinstance(c,Node):
                if (tag is None or c.tag==tag) and all(c.attrs.get(k)==v for k,v in attrs.items()):
                    yield c
                yield from c.find(tag,**attrs)
    def ancestor(self, tag=None, **attrs):
        node=self.parent
        while node:
            if (tag is None or node.tag==tag) and all(node.attrs.get(k)==v for k,v in attrs.items()):
                return node
            node=node.parent


class DOM(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.root=Node();self.current=self.root
        self.feed(raw)
    def handle_starttag(self, tag, attrs):
        node=Node(tag,attrs,self.current);self.current.children.append(node)
        if tag not in VOID:self.current=node
    def handle_startendtag(self, tag, attrs):
        node=Node(tag,attrs,self.current);self.current.children.append(node)
    def handle_endtag(self, tag):
        node=self.current
        while node is not self.root:
            if node.tag==tag:
                self.current=node.parent;return
            node=node.parent
    def handle_data(self, data):
        self.current.children.append(data)
