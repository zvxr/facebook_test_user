class FacebookResponseError(Exception):
    """ Response from Facebook API contained an error. """
    pass


class FacebookNotFoundError(Exception):
    """ Data expected from Facebook API response not found. """
    pass