from app.ratelimit import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_per_client_limit_and_window_reset():
    clock = FakeClock()
    rl = RateLimiter(per_client_per_minute=3, global_per_day=100, clock=clock)
    assert [rl.check("a") for _ in range(3)] == [None, None, None]
    reason, retry_after = rl.check("a")
    assert reason == "client" and 1 <= retry_after <= 61
    assert rl.check("b") is None  # other clients unaffected
    clock.t += 61
    assert rl.check("a") is None


def test_global_daily_cap():
    clock = FakeClock()
    rl = RateLimiter(per_client_per_minute=100, global_per_day=2, clock=clock)
    assert rl.check("a") is None
    assert rl.check("b") is None
    assert rl.check("c")[0] == "daily"
    clock.t += 86401
    assert rl.check("c") is None


def test_blocked_requests_do_not_consume_quota():
    clock = FakeClock()
    rl = RateLimiter(per_client_per_minute=1, global_per_day=2, clock=clock)
    assert rl.check("a") is None
    assert rl.check("a")[0] == "client"
    assert rl.check("a")[0] == "client"
    assert rl.check("b") is None  # a's blocked attempts didn't eat the global quota
