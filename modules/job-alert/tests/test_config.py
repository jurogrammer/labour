from job_alert.config import RUN_REQUIRED_ENVS, missing_envs


def test_storage_state_secret_is_optional() -> None:
    assert "HOJUBADA_STORAGE_STATE_B64" not in RUN_REQUIRED_ENVS


def test_missing_envs_ignores_optional_storage_state() -> None:
    env = {
        "SLACK_WEBHOOK_URL": "https://hooks.slack.test/services/mock",
        "WOORIMEL_ID": "a",
        "WOORIMEL_PW": "b",
        "MELBSKY_ID": "c",
        "MELBSKY_PW": "d",
        "HOJUBADA_ID": "e",
        "HOJUBADA_PW": "f",
    }
    assert missing_envs(RUN_REQUIRED_ENVS, environ=env) == []
