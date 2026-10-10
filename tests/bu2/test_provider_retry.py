from stratum.services.bu_v2_provider import ProviderError, ProviderUnavailable, call_with_retry


def _err(code):
    e = ProviderError(f"x: HTTP {code}")
    e.http_status = code
    return e


def test_retries_429_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _err(429)
        return "ok"

    assert call_with_retry(fn, attempts=5, base=0, sleep=lambda s: None) == "ok"
    assert len(calls) == 3


def test_does_not_retry_400():
    calls = []

    def fn():
        calls.append(1)
        raise _err(400)

    try:
        call_with_retry(fn, attempts=5, base=0, sleep=lambda s: None)
    except ProviderError:
        pass
    assert len(calls) == 1


def test_no_api_key_is_permanent():
    calls = []

    def fn():
        calls.append(1)
        raise ProviderUnavailable("p: no API key (X unset)")

    try:
        call_with_retry(fn, attempts=4, base=0, sleep=lambda s: None)
    except ProviderError:
        pass
    assert len(calls) == 1
