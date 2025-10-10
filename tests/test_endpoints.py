import io
from app import app

def test_home_ok():
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200

def test_upload_text_ok():
    client = app.test_client()
    data = {
        "textcontent": "Este é um texto de teste sem ofensa."
    }
    r = client.post("/upload/text", data=data)
    assert r.status_code == 200
    assert r.is_json
    assert r.json.get("ok") is True

def test_upload_photo_ok():
    client = app.test_client()
    fake_img = io.BytesIO(b"\x89PNG\r\n\x1a\n")  # header PNG mínimo
    data = {
        "photo": (fake_img, "teste.png")
    }
    r = client.post("/upload/photo", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.is_json
    assert r.json.get("ok") is True
