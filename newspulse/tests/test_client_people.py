from test_customer_onboarding import setup


def test_customer_people_are_persisted_and_scoped(setup):
    web, _ = setup
    auth = ('agency', 'test-password')
    body = dict(name='Anna Beispiel', email='anna@example.com', phone='+49 12345', position='Leitung', topics='Unternehmenskommunikation', media_contact=True)
    assert web.post('/client/1/people', json=body).status_code == 401
    result = web.post('/client/1/people', auth=auth, json=body)
    assert result.status_code == 200, result.text
    person = result.json()
    assert person.items() >= body.items()
    assert web.get('/client/1/people', auth=auth).json() == [person]
    assert web.get('/client/2/people', auth=auth).json() == []
    path = f"/client/1/people/{person['id']}"
    assert web.put(path.replace('/client/1/', '/client/2/'), auth=auth, json=body).status_code == 404
    body['media_contact'] = False
    assert web.put(path, auth=auth, json=body).json()['media_contact'] is False
    assert web.post('/client/1/people', auth=auth, json={**body, 'name':'   '}).status_code == 422
