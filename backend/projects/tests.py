import pytest
from rest_framework.test import APIClient
from users.models import User
from projects.models import Project, Membership, Task, Comment


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email='meera@taskboard.dev', name='Meera Iyer', password='password123')


@pytest.fixture
def auth_client(client, user):
    response = client.post('/api/auth/login', {
        'email': 'meera@taskboard.dev',
        'password': 'password123',
    }, format='json')
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['token']}")
    return client


@pytest.mark.django_db
class TestProjects:
    def test_create_project(self, auth_client, user):
        response = auth_client.post('/api/projects', {'name': 'My Project'}, format='json')
        assert response.status_code == 201
        assert response.data['project']['name'] == 'My Project'

    def test_list_only_returns_member_projects(self, auth_client, user):
        p1 = Project.objects.create(name='Mine', owner=user)
        Membership.objects.create(user=user, project=p1, role='admin')
        other = User.objects.create_user(email='other@example.com', name='Other', password='password123')
        p2 = Project.objects.create(name='Not Mine', owner=other)
        Membership.objects.create(user=other, project=p2, role='admin')

        response = auth_client.get('/api/projects')
        assert response.status_code == 200
        names = [p['name'] for p in response.data['projects']]
        assert 'Mine' in names
        assert 'Not Mine' not in names

    def test_get_project_detail(self, auth_client, user):
        project = Project.objects.create(name='My Project', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        response = auth_client.get(f'/api/projects/{project.id}')
        assert response.status_code == 200
        assert response.data['project']['name'] == 'My Project'

    def test_non_member_cannot_view_project(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='Private', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')

        resp = client.post('/api/auth/login', {'email': 'meera@taskboard.dev', 'password': 'password123'}, format='json')
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['token']}")

        response = client.get(f'/api/projects/{project.id}')
        assert response.status_code == 403


@pytest.mark.django_db
class TestTasks:
    def test_create_task(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        response = auth_client.post(f'/api/projects/{project.id}/tasks', {'title': 'Do a thing'}, format='json')
        assert response.status_code == 201
        assert response.data['task']['title'] == 'Do a thing'

    def test_update_task(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(
            project=project,
            title='Original title',
            description='Original description',
            created_by=user,
        )

        response = auth_client.patch(
            f'/api/tasks/{task.id}',
            {'title': 'Updated title', 'status': 'in_progress'},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['task']['title'] == 'Updated title'
        assert response.data['task']['status'] == 'in_progress'
        assert response.data['task']['description'] == 'Original description'
        task.refresh_from_db()
        assert task.title == 'Updated title'
        assert task.status == 'in_progress'

    def test_update_task_rejects_invalid_status(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)

        response = auth_client.patch(
            f'/api/tasks/{task.id}',
            {'status': 'blocked'},
            format='json',
        )

        assert response.status_code == 400
        task.refresh_from_db()
        assert task.status == 'todo'

    def test_update_nonexistent_task_returns_not_found(self, auth_client):
        import uuid

        response = auth_client.patch(
            f'/api/tasks/{uuid.uuid4()}',
            {'title': 'Updated title'},
            format='json',
        )

        assert response.status_code == 404

    def test_viewers_cannot_create_tasks(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')

        resp = client.post('/api/auth/login', {'email': 'meera@taskboard.dev', 'password': 'password123'}, format='json')
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['token']}")

        response = client.post(f'/api/projects/{project.id}/tasks', {'title': 'A task'}, format='json')
        assert response.status_code == 403

    def test_delete_task_requires_membership(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=owner)

        resp = client.post('/api/auth/login', {'email': 'meera@taskboard.dev', 'password': 'password123'}, format='json')
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['token']}")

        response = client.delete(f'/api/tasks/{task.id}')
        assert response.status_code == 403


@pytest.mark.django_db
class TestTaskComments:
    def test_member_can_create_and_list_task_comments(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)

        create_response = auth_client.post(
            f'/api/tasks/{task.id}/comments',
            {'content': '  First comment  '},
            format='json',
        )

        assert create_response.status_code == 201
        assert create_response.data['comment']['content'] == 'First comment'
        assert create_response.data['comment']['author']['id'] == str(user.id)

        list_response = auth_client.get(f'/api/tasks/{task.id}/comments')

        assert list_response.status_code == 200
        assert len(list_response.data['comments']) == 1
        assert list_response.data['comments'][0]['content'] == 'First comment'

    def test_viewer_can_list_but_cannot_create_comments(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')
        task = Task.objects.create(project=project, title='A task', created_by=owner)
        Comment.objects.create(task=task, author=owner, content='Existing comment')

        login_response = client.post(
            '/api/auth/login',
            {'email': user.email, 'password': 'password123'},
            format='json',
        )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['token']}")

        list_response = client.get(f'/api/tasks/{task.id}/comments')
        create_response = client.post(
            f'/api/tasks/{task.id}/comments',
            {'content': 'Viewer comment'},
            format='json',
        )

        assert list_response.status_code == 200
        assert list_response.data['comments'][0]['content'] == 'Existing comment'
        assert create_response.status_code == 403

    def test_non_member_cannot_list_task_comments(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=owner)

        login_response = client.post(
            '/api/auth/login',
            {'email': user.email, 'password': 'password123'},
            format='json',
        )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['token']}")

        response = client.get(f'/api/tasks/{task.id}/comments')

        assert response.status_code == 403

    def test_comment_creation_rejects_blank_content(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)

        response = auth_client.post(
            f'/api/tasks/{task.id}/comments',
            {'content': '   '},
            format='json',
        )

        assert response.status_code == 400
