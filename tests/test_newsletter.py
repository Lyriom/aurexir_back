def test_alta_nueva_da_201(client):
    res = client.post("/newsletter", json={"email": "news@test.com", "locale": "es"})
    assert res.status_code == 201


def test_alta_repetida_es_idempotente_y_da_200(client):
    assert (
        client.post("/newsletter", json={"email": "news@test.com", "locale": "en"}).status_code
        == 201
    )
    res = client.post("/newsletter", json={"email": "News@Test.com", "locale": "en"})
    assert res.status_code == 200


def test_email_invalido_da_422(client):
    assert (
        client.post("/newsletter", json={"email": "no-es-email", "locale": "en"}).status_code == 422
    )
