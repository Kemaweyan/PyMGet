import unittest

from pymget.utils import *

class TestSingleton(unittest.TestCase):

    def test_singeton_without_arguments(self):
        @singleton
        class Foo: pass
        self.assertEqual(Foo(), Foo())

    def test_singeton_with_args(self):
        @singleton
        class Foo:
            def __init__(_self, *args): pass
        self.assertIs(Foo(1), Foo(1))

    def test_singeton_with_kwargs(self):
        @singleton
        class Foo:
            def __init__(_self, **kwargs): pass
        self.assertIs(Foo(bar=2), Foo(bar=2))

    def test_singeton_with_args_and_kwargs(self):
        @singleton
        class Foo:
            def __init__(_self, *args, **kwargs): pass
        self.assertIs(Foo(1, bar=2), Foo(1, bar=2))


class TestCalcSize(unittest.TestCase):

    def test_calc_size_with_bytes(self):
        self.assertEqual(calc_size(1023), '1023B')

    def test_calc_size_with_kylobytes(self):
        self.assertEqual(calc_size(10000), '9.77KiB')

    def test_calc_size_with_megabytes(self):
        self.assertEqual(calc_size(10000000), '9.54MiB')

    def test_calc_size_with_gigabytes(self):
        self.assertEqual(calc_size(10000000000), '9.31GiB')

    def test_calc_size_with_terabytes(self):
        self.assertEqual(calc_size(10000000000000), '9.09TiB')


class TestCalcEta(unittest.TestCase):

    def test_calc_eta_with_zero(self):
        self.assertEqual(calc_eta(0), ' ETA: ---')

    def test_calc_eta_with_seconds(self):
        self.assertEqual(calc_eta(59), ' ETA: 59s')

    def test_calc_eta_with_minutes(self):
        self.assertEqual(calc_eta(100), ' ETA:  2m')

    def test_calc_eta_with_hours(self):
        self.assertEqual(calc_eta(39622), ' ETA: 11h')

    def test_calc_eta_with_days(self):
        self.assertEqual(calc_eta(146880), ' ETA:  2d')

    def test_calc_eta_with_weeks(self):
        self.assertEqual(calc_eta(3287363), ' ETA:  5w')

    def test_calc_eta_with_more_than_99_weeks(self):
        self.assertEqual(calc_eta(59875201), ' ETA: ---')

if __name__ == '__main__':
    unittest.main()
