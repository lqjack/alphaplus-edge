import os
import unittest


class DatabaseUrlContractTest(unittest.TestCase):
    def test_infer_db_type_from_postgresql_url(self):
        from core.database_url import infer_db_type_from_url

        self.assertEqual(
            infer_db_type_from_url("postgresql+psycopg://postgres:postgres@127.0.0.1:5432/dataproai"),
            "postgresql",
        )

    def test_postgresql_url_does_not_require_pymysql(self):
        from core.database_url import ensure_sql_driver

        ensure_sql_driver("postgresql+psycopg://postgres:postgres@127.0.0.1:5432/dataproai")

    def test_mysql_url_requires_pymysql_when_missing(self):
        from core.database_url import ensure_sql_driver

        try:
            import pymysql  # noqa: F401
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                ensure_sql_driver("mysql+pymysql://u:p@127.0.0.1:3306/db")
            self.assertIn("pymysql", str(ctx.exception).lower())
        else:
            ensure_sql_driver("mysql+pymysql://u:p@127.0.0.1:3306/db")


if __name__ == "__main__":
    unittest.main()
