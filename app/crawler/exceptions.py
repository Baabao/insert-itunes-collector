class CrawlerUnavailable(Exception):
    pass


class CrawlerBlockException(CrawlerUnavailable):
    pass


class CrawlerNotFoundException(CrawlerUnavailable):
    pass


class FeedException(Exception):
    pass


class FeedBozoException(FeedException):
    pass
