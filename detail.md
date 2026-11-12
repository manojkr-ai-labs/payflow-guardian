
| Role    | Email                                              | Password             |
| ------- | -------------------------------------------------- | -------------------- |
| Owner   | [owner@payflow.test](mailto:owner@payflow.test)     | owner-test-example   |
| Support | [support@payflow.test](mailto:support@payflow.test) | support-test-example |
This database is a new Postgres instance, so the old SQLite payments are not in it. Sign in again as owner@payflow.test with the password in apps/api/app/modules/auth/seed.py.

DEMO_MERCHANT_NAME = "PayFlow Demo Shop"
DEMO_ACCOUNTS = (
    {
        "email": "owner@payflow.test",
        "display_name": "Demo Owner",
        "password": "owner-test-example",
        "role": "owner",
    },
    {
        "email": "support@payflow.test",
        "display_name": "Demo Support",
        "password": "support-test-example",
        "role": "support",
    },
)