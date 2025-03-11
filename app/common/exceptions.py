from core.db.utils import Error


# ### main ###
class FlowError(Exception):
    pass


class ExcludeItemError(FlowError):
    pass


# ### db operation ###


class DatabaseInsertError(Error):
    pass


class DatabaseRemoveError(Error):
    pass


# ### feed parser ###


class FormatterException(Exception):
    pass


class FeedResultException(Exception):
    pass


class FeedResultFieldNotFoundError(FeedResultException):
    pass


class FeedResultTypeError(FeedResultException):
    pass


# ### collector (itunes data) ###


class ItunesDataError(Exception):
    pass


class ItunesDataFieldNotFoundError(ItunesDataError):
    pass
