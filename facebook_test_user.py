import json
import requests

from config import FB_APP_ID, FB_APP_SECRET, FB_HOST
from log import logging


class FacebookAPIError(Exception):
    pass


class FacebookUserAccess(object):
    """
    Handles all user token and code activity through Facebook Graph API.
    This only works with test users.
    """

    def __init__(self, **kwargs):
        """
        instantiated with keyword arguments:
            id                        id of the test user. Logs warning if not passed.
            app_access_token          application access token; fetches from API if not passed.
            access_token              short term user access token.
            long_term_access_token    long term user access token.
            access_code               user access code.
        """
        self.id = kwargs.get('id')
        self.app_access_token = kwargs.get('app_access_token', FacebookUserAccess.get_app_access_token())
        self.access_token = kwargs.get('access_token')
        self.long_term_access_token = kwargs.get('long_term_access_token')
        self.access_code = kwargs.get('access_code')

        if not self.id:
            logging.warn("FacebookUserAccess instantiated without id.")

    @staticmethod
    def get_app_access_token():
        """
        Calls API and returns application access token.
        Requires constants FB_APP_ID and FB_APP_SECRET to be set.
        """
        url = FB_HOST + "/oauth/access_token"

        params = {'client_id': FB_APP_ID,
                  'client_secret': FB_APP_SECRET,
                  'grant_type': 'client_credentials'}

        response = requests.get(url, params=params)
        logging.debug("get_app_access_token response: %s" % response.text)

        # Parse response and find token.
        for response_part in response.text.split('&'):
            split_response_part = response_part.split('=')
            if len(split_response_part) == 2 and split_response_part[0] == 'access_token':
                return split_response_part[1]

        # Could not locate access token.
        raise FacebookAPIError("Could not determine application access token from response: %r." % response.text)

    @property
    def access_token(self):
        if not self._access_token:
            self._access_token = self.get_access_token()
        return self._access_token

    @access_token.setter
    def access_token(self, access_token):
        self._access_token = access_token

    @property
    def long_term_access_token(self):
        if not self._long_term_access_token:
            self._long_term_access_token = self.get_long_term_access_token()
        return self._long_term_access_token

    @long_term_access_token.setter
    def long_term_access_token(self, long_term_access_token):
        self._long_term_access_token = long_term_access_token

    @property
    def access_code(self):
        if not self._access_code:
            self._access_code = self.get_access_code()
        return self._access_code

    @access_code.setter
    def access_code(self, access_code):
        self._access_code = access_code

    def get_access_token(self):
        """
        Calls API to get user's short-term access token from list of test users.
        """
        url = FB_HOST + "/%s/accounts/test-users" % FB_APP_ID
        params = {'access_token': self.app_access_token}
        response = requests.get(url, params=params)
        logging.debug("generate_short_user_token response: %s" % response.text)

        # Find test user.
        for user in response.json().get('data'):
            if user.get('id') == str(self.id):
                access_token = user.get('access_token')
                if not access_token:
                    raise FacebookAPIError("User %s located, but does not have access_token." % self.id)
                logging.debug("user access_token: %s" % access_token)
                return access_token

        raise FacebookAPIError("Unable to find user %s from response." % self.id)

    def get_long_term_access_token(self):
        """
        Calls API to exchange user's short-term for long-term access token.
        """
        url = FB_HOST + "/oauth/access_token"
        params = {'grant_type': 'fb_exchange_token',
                  'client_id': FB_APP_ID,
                  'client_secret': FB_APP_SECRET,
                  'fb_exchange_token': self.access_token}
        response = requests.get(url, params=params)
        logging.debug("get_long_term_access_token response: %s" % response.text)

        # Parse response looking for the actual token.
        for response_param in response.text.split('&'):
            name, value = response_param.partition('=')[::2]
            if name == "access_token":
                return value

        raise FacebookAPIError("Unable to find access token from response.")

    def get_access_code(self, redirect_uri=""):
        """
        Calls API using long-term access token to get access code.
        Takes and passes one parameter to API:
            redirect_uri    Defaults to empty string.
        """
        url = FB_HOST + "/oauth/client_code"
        params = {'access_token': self.long_term_access_token,
                  'client_id': FB_APP_ID,
                  'client_secret': FB_APP_SECRET,
                  'redirect_uri': redirect_uri}
        response = requests.get(url, params=params)
        logging.debug("get_access_code response: %s" % response.text)

        try:
            response_dict = response.json()
        except ValueError:
            raise FacebookAPIError("Unexpected response. No JSON object could be decoded.")

        if 'error' in response_dict:
            raise FacebookAPIError("Error in response: %r" % response_dict['error'])

        access_code = response_dict.get('code')

        if not access_code:
            logging.warn("No access_code in response.")

        return access_code


class TestUser(object):
    """
    A lightweight class for creating and utilizing Facebook test users through
    Facebook Graph API.
    """
    # Default values. Setting to None will create no default.
    generate_user_installed = True
    generate_user_permissions = 'email'
    generate_name = None
    generate_user_locale = 'en_US'
    generate_user_owner_access_token = None
    generate_user_id = None

    def __init__(self, **kwargs):
        """
        Creates a test user.
        """
        # Set application access token.
        self.app_access_token = kwargs.get('app_access_token', FacebookUserAccess.get_app_access_token())

        # Set object control variables.
        self.delete_user = kwargs.get('delete_user', True)

        # Create test user.
        test_user = TestUser.generate_user(self, **kwargs)
        self.id = test_user.get('id')
        self.login_url = test_user.get('login_url')
        self.email = test_user.get('email')
        self.password = test_user.get('password')

        # Instantiate user access.
        self.user_access = FacebookUserAccess(app_access_token=self.app_access_token,
                                              id=self.id,
                                              access_token=test_user.get('access_token'))

    def __del__(self):
        """
        Deletes user.
        """
        if self.delete_user:
            url = FB_HOST + "/%s" % self.id
            params = {'access_token': self.app_access_token}
            response = requests.delete(url, params=params)
            logging.info("delete user: %s" % response.text)
        else:
            logging.info("delete user: false")

        return

    def generate_user(self, **kwargs):
        """
        Calls API to generate a new test user.
        Returns response as dictionary.
        """
        url = FB_HOST + "/%s/accounts/test-users" % FB_APP_ID

        params = {'installed': bool(kwargs.get('installed', TestUser.generate_user_installed)),
                  'permissions': kwargs.get('permissions', TestUser.generate_user_permissions),
                  'name': kwargs.get('name', TestUser.generate_name),
                  'locale': kwargs.get('locale', TestUser.generate_user_locale),
                  'id': kwargs.get('id', TestUser.generate_user_id),
                  'access_token': self.app_access_token}

        params = dict((k, v) for k, v in params.iteritems() if v)  # Remove empty parameters.
        response = requests.post(url, params=params)
        logging.debug("generate_user response: %s" % response.text)
        response_dict = response.json()

        if 'error' in response_dict:
            raise FacebookAPIError("Error generating test user: %s" % response_dict['error'])

        return response_dict

def test():
    logging.info("Fetching app_access_token...")
    app_access_token = FacebookUserAccess.get_app_access_token()

    logging.info("Generating test user...")
    testuser = TestUser(app_access_token=app_access_token)

    logging.info("Getting short term user token...")
    testuser.user_access.access_token

    logging.info("Getting long term user token...")
    testuser.user_access.long_term_access_token

    logging.info("Getting access code...")
    testuser.user_access.access_code

if __name__ == "__main__":
    test()
