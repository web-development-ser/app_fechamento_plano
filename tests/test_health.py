def test_health_ok_com_banco(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_health_503_sem_banco():
    from app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "x",
                      "DATABASE_URL": "postgresql://x:y@127.0.0.1:1/nada?connect_timeout=2"})
    r = app.test_client().get("/health")
    assert r.status_code == 503
