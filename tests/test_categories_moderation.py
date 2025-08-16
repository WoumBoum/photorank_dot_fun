import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Category, User


def set_mod_env(user: User):
    os.environ['MODERATOR_PROVIDER'] = user.provider
    os.environ['MODERATOR_PROVIDER_ID'] = str(user.provider_id)


def test_moderator_can_update_category(authorized_client: TestClient, session: Session, test_user):
    # Make test_user the moderator
    set_mod_env(test_user)
    # Create a category owned by someone else
    other = User(email='o@example.com', username='other', provider='github', provider_id='oid')
    session.add(other)
    session.commit()
    cat = Category(name='fashion', question='Which outfit?', owner_id=other.id)
    session.add(cat)
    session.commit()

    token = authorized_client.headers.get('Authorization').split(' ')[1]

    res = authorized_client.patch(f"/api/categories/{cat.id}", json={"name":"style","question":"Which style?"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['name'] == 'style'
    assert data['question'] == 'Which style?'

    # Verify in DB
    refreshed = session.query(Category).get(cat.id)
    assert refreshed.name == 'style'
    assert refreshed.question == 'Which style?'


def test_non_moderator_forbidden_update(authorized_client: TestClient, session: Session, test_user):
    # Ensure env does not match this user
    os.environ['MODERATOR_PROVIDER'] = 'github'
    os.environ['MODERATOR_PROVIDER_ID'] = 'some-other-id'

    cat = Category(name='cars', question='Which car?', owner_id=test_user.id)
    session.add(cat)
    session.commit()

    res = authorized_client.patch(f"/api/categories/{cat.id}", json={"name":"autos"})
    assert res.status_code == 403


def test_unique_name_enforced(authorized_client: TestClient, session: Session, test_user):
    set_mod_env(test_user)
    c1 = Category(name='dogs', question='Which dog?', owner_id=test_user.id)
    c2 = Category(name='cats', question='Which cat?', owner_id=test_user.id)
    session.add_all([c1, c2])
    session.commit()

    res = authorized_client.patch(f"/api/categories/{c2.id}", json={"name":"dogs"})
    assert res.status_code == 400
    assert 'exists' in res.json()['detail']
