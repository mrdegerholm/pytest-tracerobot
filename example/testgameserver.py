#!/usr/bin/env python3
import requests
import pytest
import logging

def get(d, key):
    """ A helper function to get a key from dict or to return None if not found. """

    if key in d:
        return d[key]
    else:
        return None

class GameServerTester:
    """ Game Server Acceptance Tests """

    TEST_URL = "http://localhost:5000/game"

    def __init__(self, url=TEST_URL):
        self._url = url

    @staticmethod
    def apicall(url, params, method):
        fun = requests.post if method == "POST" else requests.get
        r = fun(url, params=params)
        logging.info(url + ': http status=%i' % r.status_code)
        if r.status_code == requests.codes.ok:
            j = r.json()
            logging.info('\tresult=%s' % j)
            return j
        else:
            return None

    class Login:
        """ Login API tester. """
        TEST_USER = "markku"
        TEST_PASS = "3l1t3"

        def __init__(self, url, user = TEST_USER, passw = TEST_PASS):
            self._url = url
            self._user = user
            self._passw = passw
            self._token = None

        def attempt(self, method = "POST"):
            params = {'user': self._user, 'pass': self._passw}
            j = GameServerTester.apicall(
                self._url + "/login", params, method)
            if j:
                is_ok = get(j, "status") == 'OK' and get(j, "token")
                if is_ok:
                    self._token = get(j, "token")
                    return True

            return False

        def logout(self):
            assert self._token
            params = {'token': self._token}
            j = GameServerTester.apicall(
                self._url + "/logout", params, "POST")
            return j and get(j, "status") == "OK"

        def get_last_token(self):
            return self._token

    class GameLobby:
        """ Game lobby API tester. """

        def __init__(self, url, login):
            self._url = url
            self._login = login
            self._nickname = None

        def set_nickname(self, nickname):
            self._nicname = nickname

        def try_register(self, token=None, method='POST'):
            token = token if token else self._login.get_last_token()
            params = {'token': token}

            if self._nickname:
                params['alias'] = self._nickname

            j = GameServerTester.apicall(
                self._url + "/register", params, method)
            if j:
                is_ok = get(j, "status") == 'OK'
                return is_ok

            return False

        def try_unregister(self):
            token = self._login.get_last_token()
            params = {'token': token}

            j = GameServerTester.apicall(
                self._url + "/unregister", params, 'POST')
            if j:
                is_ok = get(j, "status") == 'OK'
                return is_ok

            return False

    def try_login(self, user, passw, method='POST'):
        login = self.Login(self._url, user, passw)
        is_success = login.attempt(method)
        if is_success:
            login.logout()
        return is_success

    def do_login(self):
        login = self.Login(self._url)
        assert(login.attempt())
        assert(login.get_last_token())
        assert(len(login.get_last_token()) == 32)
        return login

    def get_lobby(self, login):
        return self.GameLobby(self._url, login)


@pytest.fixture(scope="module")
def gameServerFixture():
    testGameServer = GameServerTester()
    yield testGameServer


@pytest.fixture
def gameLobbyFixture():
    testGameServer = GameServerTester()
    login = testGameServer.do_login()
    yield testGameServer.get_lobby(login)
    login.logout()


@pytest.mark.credentials
def test_empty_creds(gameServerFixture):
    assert not gameServerFixture.try_login(user="", passw="")


@pytest.mark.credentials
def test_valid_creds_z(gameServerFixture):
    assert gameServerFixture.try_login(user="markku", passw="3l1t3")


@pytest.mark.credentials
def test_valid_creds_wrong_method(gameServerFixture):
    assert not gameServerFixture.try_login(
        user="markku", passw="3l1t3", method='GET')

@pytest.mark.lobby
def test_lobby_register(gameLobbyFixture):
    assert gameLobbyFixture.try_register()


@pytest.mark.lobby
def test_lobby_register_bad_token(gameLobbyFixture):
    assert not gameLobbyFixture.try_register(token="12345678")


@pytest.mark.lobby
def test_lobby_register_twice(gameLobbyFixture):
    assert gameLobbyFixture.try_register()
    assert not gameLobbyFixture.try_register()


@pytest.mark.lobby
def test_lobby_register_unregister(gameLobbyFixture):
    assert gameLobbyFixture.try_register()
    assert gameLobbyFixture.try_unregister()
