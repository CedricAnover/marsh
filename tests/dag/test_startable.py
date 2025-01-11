from marsh.dag import Startable


def test_startable_abstract():
    class TestStartable(Startable):
        def start(self):
            return "Test started"

    startable = TestStartable("test")
    assert startable.name == "test"
    assert startable.start() == "Test started"
