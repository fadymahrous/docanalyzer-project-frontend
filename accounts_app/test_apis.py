import requests
import pytest

@pytest.fixture
def access_token_fulluser():
    data={'username_or_email':'fady','password':'hidden_secret@w0rld'}
    url='http://127.0.0.1:8000/api/requesttoken/'
    response=requests.post(url,data=data)
    response_json=response.json().get('data')
    return response_json['access']

def test_create_user():
    url = "http://127.0.0.1:8000/api/createuser/"
    payload = {
        "username": "fady",
        "email": "fady@example.com",
        "password": "hidden_secret@w0rld",
        "last_name": "Mahrous",
        "birthdate": "1992-01-27",
        "nationalid": "77777",
        "phonenumber": "+49 15259027585"
    }
    request=requests.post(url,data=payload)
    assert request.status_code==201

def test_token():
    url='http://localhost:8000/api/requesttoken/'
    payload={"username_or_email":"fady@example.com","password":"hidden_secret@w0rld"}
    response=requests.post(url,data=payload)
    assert response.status_code==200
    assert isinstance(response.json(),dict)



def test_update_user(access_token_fulluser):
    url = "http://127.0.0.1:8000/api/updateuser/"
    headers={"Authorization": f"Bearer {access_token_fulluser}"}
    payload = {
        "nationalid": "1234",
    }
    response=requests.put(url,headers=headers,data=payload)
    assert response.status_code==200

def test_delete_user(access_token_fulluser):
    url = "http://127.0.0.1:8000/api/deleteuser/"
    headers={"Authorization": f"Bearer {access_token_fulluser}"}
    response=requests.delete(url,headers=headers)
    assert response.status_code==200
