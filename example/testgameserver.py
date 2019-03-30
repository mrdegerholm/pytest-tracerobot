from tracerobot.decorators import keyword, KeywordClass
import requests
import pytest

@keyword
def rlog(msg):
    print(msg)
    pass

class GameServerTester(KeywordClass):
    """ Game Server Acceptance Tests """

    def __init__(self, url):
        self._url = url

    class Login(KeywordClass):

        def __init__(self, url, user, passw):
            self._url = url
            self._user = user
            self._passw = passw

        def attempt(self):
            params = {'user': self._user, 'pass': self._passw}
            r = keyword(requests.get)(self._url, params=params)

            rlog('http status=%i' % r.status_code)
            if r.status_code == requests.codes.ok:
                j = r.json()
                rlog('result=%s' % j)
                return 'status' in j and j['status'] == 'OK'

            return False

    def try_login(self, user, passw):
        login = self.Login(self._url + "/login", user, passw)
        return login.attempt()


@pytest.fixture(scope="module")
def testGameServerFixture():
    rlog("testGameServerFixture setup")
    testGameServer = GameServerTester("http://localhost:5000/game")
    yield testGameServer
    rlog("testGameServerFixture teardown")

@pytest.fixture(scope="module")
def testFixture1():
    rlog("testFixture1 setup")
    yield None
    rlog("testFixture1 teardown")

@pytest.fixture(scope="module")
def testFixture2():
    rlog("testFixture2 setup")
    yield None
    rlog("testFixture2 teardown")

def test_nop():
    rlog("nop!")

def test_empty_creds(testGameServerFixture, testFixture1):
    assert not testGameServerFixture.try_login(user="", passw="")

def test_valid_creds(testGameServerFixture, testFixture2):
    assert testGameServerFixture.try_login(user="markku", passw="3l1t3")
