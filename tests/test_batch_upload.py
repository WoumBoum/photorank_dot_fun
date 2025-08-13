import io
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def make_image_bytes(color=(255,0,0)):
    img = Image.new('RGB', (10, 10), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_batch_upload_session_requires_auth():
    resp = client.post('/api/photos/upload/session/batch')
    assert resp.status_code in (401, 403)


def test_batch_upload_session_happy_flow(auth_headers, select_category_session):
    files = [('files', ('a.png', make_image_bytes().read(), 'image/png')) for _ in range(3)]
    resp = client.post('/api/photos/upload/session/batch', headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) == 3
    for item in data:
        assert 'id' in item and 'filename' in item


def test_batch_upload_session_limit_10(auth_headers, select_category_session):
    files = [('files', ('a.png', make_image_bytes().read(), 'image/png')) for _ in range(11)]
    resp = client.post('/api/photos/upload/session/batch', headers=auth_headers, files=files)
    assert resp.status_code == 400


def test_batch_upload_session_reject_non_image(auth_headers, select_category_session):
    files = [
        ('files', ('a.png', make_image_bytes().read(), 'image/png')),
        ('files', ('b.txt', b'hello', 'text/plain')),
    ]
    resp = client.post('/api/photos/upload/session/batch', headers=auth_headers, files=files)
    assert resp.status_code == 400
