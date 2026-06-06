# -*- coding: utf-8 -*-


class NoneKeyUinError(ValueError):
    def __init__(self, *args):
        super(NoneKeyUinError, self).__init__(*args)


class AccountKeyExpireError(ValueError):
    def __init__(self, *args):
        super(AccountKeyExpireError, self).__init__(*args)


