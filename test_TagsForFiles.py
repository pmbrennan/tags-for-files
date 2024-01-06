import unittest
from unittest import TestCase

import TagsForFiles


def run_all_unit_tests():
    test_runner = unittest.TextTestRunner()
    test_cases = [TagsForFilesTest()]
    # noinspection PyTypeChecker
    suites = [unittest.TestLoader().loadTestsFromTestCase(tc) for tc in test_cases]
    for suite in suites:
        test_runner.run(suite)


if __name__ == '__main__':
    run_all_unit_tests()


class TagsForFilesTest(TestCase):
    @staticmethod
    def test_paragraph_wrap():
        result = TagsForFiles.Util.paragraph_wrap(
            "england expects     every    man to    do his     duty", 20)
        assert (result == "england expects\nevery man to do his\nduty")
