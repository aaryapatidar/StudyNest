from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def token():
    response = client.post('/api/auth/login', data={'username': 'student@studynest.edu', 'password': 'Student@123'})
    return response.json()['access_token']

def test_health():
    assert client.get('/api/health').json()['status'] == 'ok'

def test_login_and_me():
    access_token = token()
    response = client.get('/api/auth/me', headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
    assert response.json()['email'] == 'student@studynest.edu'

def test_subject_crud_requires_auth():
    assert client.get('/api/subjects').status_code == 401
    response = client.post('/api/subjects', headers={'Authorization': f'Bearer {token()}'}, json={'name': 'Testing', 'code': 'T-1', 'description': 'API test subject', 'semester': 4})
    assert response.status_code == 201
    assert response.json()['code'] == 'T-1'
