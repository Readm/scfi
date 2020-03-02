class Node():
    def __init__(self, symbol=None, weight=None, left=None, right=None, parent=None):
        self.symbol = symbol
        self.weight = weight
        self.left = left
        self.right = right
        self.parent = parent

    @property
    def code(self):
        if self.parent == None:
            return ''
        else:
            return self.parent.code + ('0' if self is self.parent.left else '1')


def codebook(iter, weight_fun=lambda x, y: x+y):
    """
    Provided an iterable of 2-tuples in (symbol, weight) format, generate a
    Huffman codebook, returned as a dictionary in {symbol: code} format.
    Examples:
    >>> codebook([('A', 2), ('B', 4), ('C', 1), ('D', 1)])
    {'A': '10', 'B': '0', 'C': '110', 'D': '111'}
    """
    available = []
    for i in iter:
        available.append(Node(symbol=i[0], weight=i[1]))

    copy=[n for n in available]

    if len(available) == 0:
        return dict([])

    while len(available) > 1:
        available.sort(key=lambda x: x.weight, reverse=True)
        r = available.pop()
        l = available.pop()
        p = Node(left=l, right=r, weight=weight_fun(l.weight, r.weight))
        l.parent = p
        r.parent = p
        available.append(p)

    return {n.symbol:n.code for n in copy} 