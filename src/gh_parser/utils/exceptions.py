class APIException(BaseException):
    def __init__(self, *args):
        super().__init__(*args)


class ConfigException(BaseException):
    def __init__(self, *args):
        super().__init__(*args)


class GHException(BaseException):
    def __init__(self, *args):
        super().__init__(*args)
