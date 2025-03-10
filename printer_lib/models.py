'Printer model specifications'

class Model():
    'A printer model'
    paper_width: int
    is_new_kind: bool
    def __init__(self, width, is_new):
        self.paper_width = width
        self.is_new_kind = is_new

Models = {
    'YT01': Model(384, False),
    'GB01': Model(384, False),
    'GB02': Model(384, False),
    'GB03': Model(384, True),
    'GT01': Model(384, False),
}
