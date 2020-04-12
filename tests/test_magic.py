from unittest.mock import Mock

import pytest
import pytest_twisted
from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, succeed
from wormhole.errors import WrongPasswordError
from wormhole.util import dict_to_bytes

from src.magic import HumanError, SuspiciousOperation, Timeout, Wormhole


@pytest.fixture
def upstream(monkeypatch):
    upstream = Mock()

    def mock_init(self):
        self.wormhole = upstream

    monkeypatch.setattr(Wormhole, '__init__', mock_init)

    return upstream


@pytest_twisted.inlineCallbacks
def test_generate_code_timeout(upstream):
    """
    The Wormhole.generate_code method should be able to handle timeouts.
    """
    def get_code():
        deferred = Deferred()
        reactor.callLater(2, deferred.callback, 'code')
        return deferred
    upstream.get_code = get_code

    wormhole = Wormhole()
    with pytest.raises(Timeout):
        yield wormhole.generate_code(timeout=0)


@pytest_twisted.inlineCallbacks
def test_generate_code_works(upstream):
    """
    The Wormhole.generate_code method should resolve into a code generated by
    the upstream if all goes well.
    """
    upstream.get_code = lambda: succeed('code')

    wormhole = Wormhole()
    res = yield wormhole.generate_code()
    assert res == 'code'


@pytest_twisted.inlineCallbacks
def test_connect_works(upstream):
    """
    The Wormhole.connect method should resolve if the upstream resolves.
    """
    upstream.get_code = lambda: succeed(None)
    wormhole = Wormhole()
    res = yield wormhole.connect('code')
    assert res is None


@pytest_twisted.inlineCallbacks
def test_exchange_keys_bad_code(upstream):
    """
    The Wormhole.exchange_keys method should be able to handle the upstream's
    WrongPasswordError.
    """
    upstream.get_verifier = lambda: fail(WrongPasswordError())

    wormhole = Wormhole()
    with pytest.raises(HumanError):
        yield wormhole.exchange_keys()


@pytest_twisted.inlineCallbacks
def test_exchange_keys_works(upstream):
    """
    The Wormhole.exchange_keys method should resolve into a verifier coming
    from the upstream if all goes well.
    """
    upstream.get_verifier = lambda: succeed('verifier')

    wormhole = Wormhole()
    res = yield wormhole.exchange_keys()
    assert res == 'verifier'


@pytest_twisted.inlineCallbacks
def test_await_json_timeout(upstream):
    """
    The Wormhole.await_json method should be able to handle timeouts.
    """
    def get_message():
        deferred = Deferred()
        reactor.callLater(2, deferred.callback, dict_to_bytes({}))
        return deferred
    upstream.get_message = get_message

    wormhole = Wormhole()
    with pytest.raises(Timeout):
        yield wormhole.await_json(timeout=0)


@pytest_twisted.inlineCallbacks
def test_await_json_bad_message(upstream):
    """
    The Wormhole.await_json method should not break if the upstream resolves
    into a message that does not conform to the wormhole spec.
    """
    upstream.get_message = lambda: succeed('some string')

    wormhole = Wormhole()
    with pytest.raises(SuspiciousOperation):
        yield wormhole.await_json()


@pytest_twisted.inlineCallbacks
def test_await_json_works(upstream):
    """
    The Wormhole.await_json method should resolve into a dict parsed from the
    upstream's return value.
    """
    upstream.get_message = lambda: succeed(dict_to_bytes({'answer': 42}))

    wormhole = Wormhole()
    res = yield wormhole.await_json()
    assert res == {'answer': 42}
