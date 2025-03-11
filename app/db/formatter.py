def program_rss_data_formatter(program_rss_data=None):
    """
    Try getting rss url, email and producer from a data
    Use None for no data cases
    """
    # Default
    rss_url = None
    producer_name = None
    email = None

    # assign value if not empty
    if program_rss_data and isinstance(program_rss_data, dict):
        if program_rss_data.get("feedUrl", None):
            rss_url = str(program_rss_data.get("feedUrl", None)).strip()
        if program_rss_data.get("artistName", None):
            producer_name = str(program_rss_data.get("artistName", None)).strip()
        if program_rss_data.get("email", None):
            email = str(program_rss_data.get("email", None)).strip()

    return rss_url, producer_name, email
