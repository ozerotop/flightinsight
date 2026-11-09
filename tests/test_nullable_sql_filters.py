"""Regression tests for PostgreSQL nullable bind-parameter filters."""
import unittest
from scripts.run_analytics import QUERIES, load_query

class NullableSqlFilterTests(unittest.TestCase):
    def test_nullable_optional_filters_are_explicitly_typed(self):
        columns = {
            "airline_code": "a.airline_code",
            "origin_code": "o.airport_code",
            "destination_code": "d.airport_code",
        }
        for name in QUERIES:
            sql = load_query(name)
            for param, column in columns.items():
                with self.subTest(query=name, param=param):
                    typed_filter = (
                        f"(CAST(%({param})s AS text) IS NULL "
                        f"OR {column} = CAST(%({param})s AS text))"
                    )
                    self.assertIn(typed_filter, sql)
                    self.assertNotIn(f"%({param})s IS NULL", sql)

    def test_date_filters_remain_typed_and_parameterized(self):
        for name in QUERIES:
            with self.subTest(query=name):
                sql = load_query(name)
                self.assertIn("CAST(%(date_from)s AS date)", sql)
                self.assertIn("CAST(%(date_to)s AS date)", sql)

if __name__ == "__main__":
    unittest.main()
