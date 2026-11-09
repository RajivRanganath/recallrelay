class BriefUnavailable(RuntimeError):
    """The brief provider could not produce a usable reply. The code is a short label, never upstream text."""

    def __init__(self, code='unavailable'):
        super().__init__('Brief provider unavailable')
        self.code = code
