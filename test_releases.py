import unittest
from check_releases import decision, source_script


class ReleaseDecisions(unittest.TestCase):
    def record(self, state='succeeded', recipe='old', tag='v1.20', serial=1):
        return {'id': 123, 'state': state,
                'meta': {'tag': tag, 'commit': 'a' * 40, 'recipe': recipe, 'release': serial}}

    def test_first_release(self):
        self.assertEqual(decision([], 'v1.20', 'a' * 40, 'old'), (True, None, 1))

    def test_success_is_not_duplicated(self):
        self.assertEqual(decision([self.record()], 'v1.20', 'a' * 40, 'old'), (False, None, 2))

    def test_failed_build_is_retried(self):
        self.assertEqual(decision([self.record('failed')], 'v1.20', 'a' * 40, 'old'), (True, None, 2))

    def test_pending_build_is_not_duplicated(self):
        self.assertEqual(decision([self.record('running')], 'v1.20', 'a' * 40, 'new'), (False, 123, 2))

    def test_recipe_change_only_rebuilds_latest(self):
        records = [self.record()]
        self.assertEqual(decision(records, 'v1.20', 'a' * 40, 'new'), (True, None, 2))
        self.assertEqual(decision(records, 'v1.20', 'a' * 40, 'new', latest=False), (False, None, 2))

    def test_retagged_release_rebuilds(self):
        self.assertTrue(decision([self.record()], 'v1.20', 'b' * 40, 'old')[0])

    def test_force_and_release_counter(self):
        records = [self.record(serial=4), self.record('failed', serial=3)]
        self.assertEqual(decision(records, 'v1.20', 'a' * 40, 'old', force=True), (True, None, 5))

    def test_other_release_does_not_hide_new_release(self):
        self.assertEqual(decision([self.record()], 'v1.21', 'b' * 40, 'old'), (True, None, 1))

    def test_source_is_pinned_and_under_copr_size_limit(self):
        script = source_script(self.record()['meta'], 'b' * 40)
        self.assertIn('b' * 40, script)
        self.assertIn('--commit ' + 'a' * 40, script)
        self.assertLess(len(script.encode()), 4000)


if __name__ == '__main__':
    unittest.main()
