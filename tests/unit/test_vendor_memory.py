"""The vendor memory: a vendor is avoided only after enough trips show it consistently quoting
well above the other vendors for the same plan."""
from rally.vendor_memory import VendorMemory


def trips(mem: VendorMemory, n: int, premium: float, user="u", start=0) -> None:
    """n trips where vendor 'hi' quotes `premium` above vendor 'lo' for the same plan."""
    for i in range(start, start + n):
        mem.observe([user], f"d{i}", [[("hi", "Pricey Co", 100 * (1 + premium)), ("lo", "Fair Co", 100)]])


def test_thirty_percent_over_is_avoided_after_three_trips_not_two():
    mem = VendorMemory()
    trips(mem, 2, 0.30)
    assert not mem.avoids("u", "hi")
    trips(mem, 1, 0.30, start=2)
    assert mem.avoids("u", "hi") and not mem.avoids("u", "lo")


def test_twenty_percent_over_needs_seven_trips():
    mem = VendorMemory()
    trips(mem, 6, 0.20)
    assert not mem.avoids("u", "hi")
    trips(mem, 1, 0.20, start=6)
    assert mem.avoids("u", "hi")


def test_ten_percent_over_is_never_avoided():
    mem = VendorMemory()
    trips(mem, 50, 0.10)
    assert not mem.avoids("u", "hi")


def test_a_vendor_that_is_sometimes_cheapest_is_not_avoided():
    mem = VendorMemory()
    trips(mem, 3, 0.80)
    for i in range(3, 6):           # three trips where it was the cheaper one
        mem.observe(["u"], f"d{i}", [[("hi", "Pricey Co", 90), ("lo", "Fair Co", 100)]])
    v = mem.verdict("u", "hi")
    assert v["aboveMarketShare"] == 0.5 and not v["avoid"]


def test_requotes_of_one_trip_count_once():
    mem = VendorMemory()
    for _ in range(5):
        trips(mem, 1, 0.50)          # the same deal "d0" quoted five times
    assert mem.verdict("u", "hi")["trips"] == 1 and not mem.avoids("u", "hi")


def test_each_person_learns_from_their_own_trips():
    mem = VendorMemory()
    trips(mem, 3, 0.50, user="kevin")
    assert mem.avoids("kevin", "hi") and not mem.avoids("ana", "hi")


def test_one_quote_alone_teaches_nothing():
    mem = VendorMemory()
    mem.observe(["u"], "d0", [[("hi", "Pricey Co", 900)], [("lo", "Fair Co", 100)]])   # never on the same plan
    assert mem.known("u") == []


def test_a_trip_is_judged_on_the_plans_vendors_share():
    mem = VendorMemory()
    for i in range(3):
        mem.observe(["u"], f"d{i}", [[("hi", "Pricey Co", 150), ("lo", "Fair Co", 100)],   # boat dive: both
                                     [("lo", "Fair Co", 60)]])                              # shore: only Fair
    v = mem.verdict("u", "hi")
    assert v["trips"] == 3 and v["avoid"]


def test_memory_survives_a_restart(tmp_path):
    path = tmp_path / "vendor_memory.json"
    trips(VendorMemory(path), 3, 0.50)
    again = VendorMemory(path)
    assert again.avoids("u", "hi") and again.verdict("u", "hi")["name"] == "Pricey Co"
