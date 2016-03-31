from common import (HTTP_OK,
                    HTTP_CREATED,
                    HTTP_ACCEPTED,
                    HTTP_NO_CONTENT,
                    HTTP_BAD_REQUEST,
                    HTTP_FORBIDDEN,
                    HTTP_NOT_FOUND,
                    HTTP_METHOD_NOT_ALLOWED)

from common import RootTestCase
from django.contrib.sites.models import Site
from django.contrib.markup.templatetags.markup import textile
from agora_site.agora_core.tasks.agora import send_request_membership_mails

class AgoraTest(RootTestCase):
    base_election_data = {
        'action': "create_election",
        'pretty_name': "foo bar",
        'description': "foo bar foo bar",
        'questions': [
            {
                'a': 'ballot/question',
                'tally_type': 'ONE_CHOICE',
                'max': 1,
                'min': 0,
                'question': 'Do you prefer foo or bar?',
                'randomize_answer_order': True,
                'answers': [
                    {
                        'a': 'ballot/answer',
                        'url': '',
                        'details': '',
                        'value': 'fo\"o'
                    },
                    {
                        'a': 'ballot/answer',
                        'url': '',
                        'details': '',
                        'value': 'bar'
                    }
                ]
            }
        ],
        'is_vote_secret': True,
        'from_date': '',
        'to_date': ''
    }

    def test_agora(self):
        # all
        data = self.getAndParse('agora/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 2)

    def test_agora_url(self):
        '''
        Test that an agora has an url
        '''
        data = self.getAndParse('agora/1/')
        self.assertEquals(data['url'], '/david/agoraone')

    def test_agora_find(self):
        # find
        data = self.getAndParse('agora/1/')
        self.assertEquals(data['name'], 'agoraone')

        data = self.getAndParse('agora/2/')
        self.assertEquals(data['name'], 'agoratwo')

        data = self.get('agora/200/', code=HTTP_NOT_FOUND)

    def test_agora_creation(self):
        # creating agora
        self.login('david', 'david')
        orig_data = {'pretty_name': '<p>created agora</p>',
                     'short_description': '<p>created agora description</p>',
                     'is_vote_secret': False}
        data = self.postAndParse('agora/', orig_data,
            code=HTTP_CREATED, content_type='application/json')

        data = self.getAndParse('agora/%s/' % data['id'])
        for k, v in orig_data.items():
            self.assertEquals(data[k], v)

        # validation error
        orig_data = {'short_description': '<p>created agora description</p>',
                     'is_vote_secret': False}
        data = self.postAndParse('agora/', orig_data,
            code=HTTP_BAD_REQUEST, content_type='application/json')

    def test_agora_removal(self):
        self.login('david', 'david')
        data = self.getAndParse('agora/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 2)

        self.delete('agora/1/', code=HTTP_NO_CONTENT)

        data = self.getAndParse('agora/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 1)

        # check permissions
        self.login('user1', '123')
        self.delete('agora/2/', code=HTTP_FORBIDDEN)
        self.login('david', 'david')
        self.delete('agora/2/', code=HTTP_NO_CONTENT)
        self.delete('agora/2/', {}, code=HTTP_NOT_FOUND)

        data = self.getAndParse('agora/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 0)

        self.delete('agora/1/', {}, code=HTTP_NOT_FOUND)
        self.delete('agora/200/', {}, code=HTTP_NOT_FOUND)

    def test_agora_removal2(self):
        self.login('david', 'david')
        # admin creates a new election
        data = self.postAndParse('agora/1/action/', data=self.base_election_data,
            code=HTTP_OK, content_type='application/json')
        election_id = data['id']

        # admin starts the election
        orig_data = dict(action='start')
        data = self.postAndParse('election/%d/action/' % election_id,
            data=orig_data, code=HTTP_OK, content_type='application/json')

        orig_data = dict(action='delegate_vote', user_id=1)
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        delegated_vote_id = data['id']

        data = self.getAndParse('action/agora/1/')
        self.assertEqual(len(data['objects']), 3)
        action0_id = data['objects'][0]['id']
        action1_id = data['objects'][1]['id']

        # election has two actions
        data = self.getAndParse('action/election/%d/' % election_id)
        self.assertEqual(len(data['objects']), 3)
        action2_id = data['objects'][0]['id']
        action3_id = data['objects'][1]['id']

        # get agora - ok
        self.get('agora/1/', code=HTTP_OK)

        # get delegated_vote - ok
        self.get('castvote/%d/' % delegated_vote_id, code=HTTP_OK)

        # get election - ok
        self.get('election/%d/' % election_id, code=HTTP_OK)

        # get actions - ok
        self.get('action/%d/' % action0_id, code=HTTP_OK)
        self.get('action/%d/' % action1_id, code=HTTP_OK)
        self.get('action/%d/' % action2_id, code=HTTP_OK)
        self.get('action/%d/' % action3_id, code=HTTP_OK)

        # delete agora
        self.delete('agora/1/', {}, code=HTTP_NO_CONTENT)

        # get agora - not found
        self.get('agora/1/', code=HTTP_NOT_FOUND)

        # get delegated_vote - not found
        self.get('castvote/%d/' % delegated_vote_id, code=HTTP_NOT_FOUND)

        # get election - not found
        self.get('election/%d/' % election_id, code=HTTP_NOT_FOUND)

        # get actions - not found
        self.get('action/%d/' % action0_id, code=HTTP_NOT_FOUND)
        self.get('action/%d/' % action1_id, code=HTTP_NOT_FOUND)
        self.get('action/%d/' % action2_id, code=HTTP_NOT_FOUND)
        self.get('action/%d/' % action3_id, code=HTTP_NOT_FOUND)

    def test_agora_update(self):
        self.login('user1', '123')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "<p>new desc</p>",
                     'is_vote_secret': False,
                     'biography': "<p>bio</p>",
                     'membership_policy': 'ANYONE_CAN_JOIN',
                     'comments_policy': 'ANYONE_CAN_COMMENT',
                     'delegation_policy': 'DISALLOW_DELEGATION'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')
        self.login('david', 'david')
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')
        data = self.getAndParse('agora/1/')
        for k, v in orig_data.items():
            self.assertEquals(data[k], v)

        # testing validation
        orig_data = {'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'ANYONE_CAN_JOIN',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_BAD_REQUEST, content_type='application/json')

    def test_agora_delegation_policy(self):
        self.login('david', 'david')

        # user2 should have some permissions
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEquals(set(data["permissions"]), set(['admin', 'delete',
            'comment', 'create_election', 'delegate', 'receive_mail']))

        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'ANYONE_CAN_JOIN',
                     'comments_policy': 'ANYONE_CAN_COMMENT',
                     'delegation_policy': 'DISALLOW_DELEGATION'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # user2 should have some permissions
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEquals(set(data["permissions"]), set(['admin', 'delete',
            'comment', 'create_election', 'receive_mail']))


    def test_agora_request_membership(self):
        self.login('user1', '123')
        orig_data = {'action': "request_membership", }
        # User cannot request membership; he can directly join instead
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        orig_data = {'action': "join", }
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        orig_data = {'action': "request_membership", }
        # user is already a member of this agora
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # Noone is requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        self.login('user2', '123')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user already requested membership
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 is requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'user2')

        # user2 stops requesting
        orig_data = {'action': "cancel_membership_request"}
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user2 is requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)


    def test_agora_accept_membership_request(self):
        '''
        Test that an admin can accept a membership request
        '''

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # requesting membership
        self.login('user2', '123')
        orig_data = dict(action='request_membership')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # trying to accept membership with an user with no permissions,
        # should fail
        self.login('user1', '123')
        orig_data = dict(action='accept_membership', username='user2')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 is still requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'user2')

        # and user2 is not a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

        # accept membership properly, should succeed
        self.login('david', 'david')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user2 is not requesting any more
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        # user2 is a member now
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user2')

    def test_agora_deny_membership_request(self):
        '''
        Test that an admin can accept a membership request
        '''

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # requesting membership
        self.login('user2', '123')
        orig_data = dict(action='request_membership')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # trying to deny membership with an user with no permissions,
        # should fail
        self.login('user1', '123')
        orig_data = dict(action='deny_membership', username='user2')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 is still requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'user2')

        # and user2 is not a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

        # deny membership properly, should succeed
        self.login('david', 'david')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user2 is not requesting any more
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        # and user2 is not a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

    def test_agora_add_membership1(self):
        '''
        Test that an admin can add a member
        '''

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # requesting membership
        self.login('user2', '123')
        orig_data = dict(action='request_membership')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # trying to add member with an user with no permissions,
        # should fail
        self.login('user1', '123')
        orig_data = dict(action='add_membership', username='user2',
            welcome_message="weeEeEeelcome!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 is still requesting
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'user2')

        # and user2 is not a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

        # add membership properly, should succeed
        self.login('david', 'david')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user2 is not requesting any more
        data = self.getAndParse('agora/1/membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        # user2 is a member now
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user2')

    def test_agora_add_membership2(self):
        '''
        Test that an admin can add a member
        '''

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # add user1, directly, without requesting membership
        orig_data = dict(action='add_membership', username='user1',
            welcome_message="weeEeEeelcome!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 is a member now
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user1')

    def test_agora_remove_membership(self):
        '''
        Test that an admin can remove a member
        '''

        # setting restricted joining policy
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
                     'comments_policy': 'ANYONE_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # add user1
        orig_data = dict(action='add_membership', username='user1',
            welcome_message="weeEeEeelcome!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 is a member now
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user1')

        # trying to remove member with an user with no permissions,
        # should fail
        self.login('user1', '123')
        orig_data = dict(action='remove_membership', username='user1',
            goodbye_message="Goodbye!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user1 is still a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user1')

        # removing membership
        self.login('david', 'david')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 is not a member anymore
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

        # removing membership from an user who is not a member
        orig_data = dict(action='remove_membership', username='user1',
            goodbye_message="Goodbye!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

    def test_agora_leave(self):
        '''
        Test an user can leave the agora
        '''

        # user1 joins
        self.login('user1', '123')
        orig_data = dict(action="join")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 is a member now
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 2)
        self.assertEquals(data['objects'][1]['username'], 'user1')

        # leave
        orig_data = dict(action="leave")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 is not a member anymore
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

        # leaving from an user who is not a member
        self.login('user2', '123')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # owner trying to leave
        self.login('david', 'david')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # owner is still a member
        data = self.getAndParse('agora/1/members/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'david')

    def test_agora_test_action(self):
        '''
        Basic tests on agora actions
        '''
        # method must be post so this fails
        data = self.get('agora/1/action/', code=HTTP_METHOD_NOT_ALLOWED)

        # no action provided so this fails
        data = self.post('agora/1/action/', data=dict(),
            code=HTTP_NOT_FOUND, content_type='application/json')

        # non existant action provided so this fails
        data = self.post('agora/1/action/', data=dict(action="3gt3g3gerr"),
            code=HTTP_NOT_FOUND, content_type='application/json')

        # test action correctly, so this succeeds
        orig_data = dict(action="test", param1="blah")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # now test action but with a inexistant agora, should fail
        data = self.post('agora/4454/action/', data=orig_data,
            code=HTTP_NOT_FOUND, content_type='application/json')

    def test_agora_get_perms(self):
        '''
        tests on agora get permissions
        '''
        orig_data = dict(action="get_permissions")

        # anonymous user has no special permissions
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEquals(set(data["permissions"]), set([]))

        # david user should have admin permissions
        self.login('david', 'david')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEquals(set(data["permissions"]),
            set(['admin', 'delete', 'comment', 'create_election', 'delegate', 'receive_mail']))

        # user2 should have some permissions
        self.login('user2', '123')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEquals(set(data["permissions"]), set(['join', 'comment', 'create_election']))

    def test_send_request_membership_mails(self):
        '''
        test the celery send_request_membership_mails function
        '''
        kwargs=dict(
            agora_id=1,
            user_id=1,
            is_secure=True,
            site_id=Site.objects.all()[0].id,
            remote_addr='127.0.0.1'
        )
        result = send_request_membership_mails.apply_async(kwargs=kwargs)
        self.assertTrue(result.successful())

    def test_add_comment1(self):
        '''
        Tests adding a comment in the agora
        '''
        # get activity - its empty
        data = self.getAndParse('action/agora/1/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 0)

        # add a comment as anonymous - fails, forbidden
        orig_data = dict(comment='blah blah blah blah.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # still no activity
        data = self.getAndParse('action/agora/1/')
        agoras = data['objects']
        self.assertEqual(len(agoras), 0)

        # add a comment as a logged in user that is a member of the agora
        self.login('david', 'david')
        data = self.postAndParse('agora/1/add_comment/', orig_data,
            code=HTTP_OK, content_type='application/json')

        # now the comment is there
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]['actor']['content_type'], 'user')
        self.assertEqual(objects[0]['actor']['username'], 'david')
        self.assertEqual(objects[0]['action_object']['content_type'], 'comment')
        self.assertEqual(objects[0]['action_object']['comment'].strip(), textile(orig_data['comment']).strip())

    def test_list_comments(self):
        '''
        Tests adding a comment in the agora and listing it
        '''
        # list comments - its empty
        data = self.getAndParse('agora/1/comments/')
        comments = data['objects']
        self.assertEqual(len(comments), 0)

        # add a comment as a logged in user that is a member of the agora
        self.login('david', 'david')
        orig_data = dict(comment='blah blah blah blah.')
        data = self.postAndParse('agora/1/add_comment/', orig_data,
            code=HTTP_OK, content_type='application/json')

        # now the comment is there
        data = self.getAndParse('agora/1/comments/')
        objects = data['objects']
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]['actor']['content_type'], 'user')
        self.assertEqual(objects[0]['actor']['username'], 'david')
        self.assertEqual(objects[0]['action_object']['content_type'], 'comment')
        self.assertEqual(objects[0]['action_object']['comment'].strip(), textile(orig_data['comment']).strip())


    def test_add_comment2(self):
        '''
        Tests adding a comment in the agora
        '''
        # no activity
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 0)

        # set comment policy to only members
        self.login('david', 'david')
        orig_data = {'pretty_name': "updated name",
                     'short_description': "new desc",
                     'is_vote_secret': False,
                     'biography': "bio",
                     'membership_policy': 'ANYONE_CAN_JOIN',
                     'comments_policy': 'ONLY_MEMBERS_CAN_COMMENT'}
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # add a comment as a non member - fails
        self.login('user1', '123')
        orig_data = dict(comment='blah blah blah blah.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # still no activity
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 0)

        # user1 joins the agora
        orig_data = dict(action="join")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # this generates "joined" and "started following" actions
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 2)

        # add a comment as a member - succeeds
        orig_data = dict(comment='blah blah blah blah 2 yeahh pirata.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_OK, content_type='application/json')

        # now the comment is there
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 3)
        self.assertEqual(objects[0]['actor']['content_type'], 'user')
        self.assertEqual(objects[0]['actor']['username'], 'user1')
        self.assertEqual(objects[0]['action_object']['content_type'], 'comment')
        self.assertEqual(objects[0]['action_object']['comment'].strip(), textile(orig_data['comment']).strip())

    def test_add_comment3(self):
        '''
        Tests adding a comment in the agora
        '''
        # set comment policy to only admins
        self.login('david', 'david')
        orig_data = {
            'pretty_name': "updated name",
            'short_description': "new desc",
            'is_vote_secret': False,
            'biography': "bio",
            'membership_policy': 'ANYONE_CAN_JOIN',
            'comments_policy': 'ONLY_ADMINS_CAN_COMMENT'
        }
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # user1 joins the agora
        self.login('user1', '123')
        orig_data = dict(action="join")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # try to post a comment as member - fails
        orig_data = dict(comment='blah blah blah blah 2 yeahh pirata.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # the comment is not there, user joined and follows
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 2) 

        # post the comment as agora admin
        self.login('david', 'david')
        orig_data = dict(comment='blah blah blah blah 2 yeahh pirata.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_OK, content_type='application/json')

        # now the comment is there
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 3)

    def test_add_comment4(self):
        '''
        Tests adding a comment in the agora
        '''
        # set comment policy to no comments
        self.login('david', 'david')
        orig_data = {
            'pretty_name': "updated name",
            'short_description': "new desc",
            'is_vote_secret': False,
            'biography': "bio",
            'membership_policy': 'JOINING_REQUIRES_ADMINS_APPROVAL',
            'comments_policy': 'NO_COMMENTS'
        }
        data = self.put('agora/1/', data=orig_data,
            code=HTTP_ACCEPTED, content_type='application/json')

        # post the comment as agora admin - fails, not even admins can post
        orig_data = dict(comment='blah blah blah blah 2 yeahh pirata.')
        data = self.post('agora/1/add_comment/', orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # the comment is not there
        data = self.getAndParse('action/agora/1/')
        objects = data['objects']
        self.assertEqual(len(objects), 0)

    def test_agora_request_admin_membership(self):
        self.login('user1', '123')
        # user1 joins the agora
        orig_data = {'action': "join", }
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 cannot check admin membership requests
        data = self.get('agora/1/admin_membership_requests/', code=HTTP_FORBIDDEN)

        orig_data = {'action': "request_admin_membership", }
        # user1 can request admin membership
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 has already requested admin membership
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # check user1 is not yet admin
        orig_data = dict(action="get_permissions")
        # anonymous user has no special permissions
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('admin' not in data['permissions'])

        # check user1 is requesting permissions
        self.login('david', 'david')
        data = self.getAndParse('agora/1/admin_membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 1)
        self.assertEquals(data['objects'][0]['username'], 'user1')

        # accept admin membership
        orig_data = dict(action='accept_admin_membership', username='user1')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # now user1 is not requesting admin permissions
        data = self.getAndParse('agora/1/admin_membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        # check user1 is admin
        self.login('user1', '123')
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('admin' in data['permissions'])

        # now it's user2 who request to be made admin, but can't because it 
        # is not a member
        self.login('user2', '123')
        orig_data = {'action': "request_admin_membership", }
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 joins the agora
        orig_data = {'action': "join", }
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # now request again, this time successfully, agora admin membership
        orig_data = {'action': "request_admin_membership", }
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 rejects the admin membership of user2. Remember user1 has admin
        # status, so he can do it
        self.login('user1', '123')
        orig_data = dict(action='deny_admin_membership', username='user2')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # check user2 is not admin
        self.login('user2', '123')
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('admin' not in data['permissions'])

        # check user1 is not requesting membership anymore
        self.login('user1', '123')
        data = self.getAndParse('agora/1/admin_membership_requests/', code=HTTP_OK)
        self.assertEquals(data['meta']['total_count'], 0)

        # user1 makes user2 admin directly
        orig_data = dict(action='add_admin_membership', username='user2',
            welcome_message="hola!")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # check user2 is admin now
        self.login('user2', '123')
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('admin' in data['permissions'])

        # user2 removes user1 from admin membership
        orig_data = dict(action='remove_admin_membership', username='user1',
            goodbye_message="adios con el corazon")
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 cannot be removed from admin any more, since it's not an admin
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user2 leaves admin
        orig_data = dict(action='leave_admin_membership')
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # you cannot leave admin twice
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # check user2 is not admin in permissions
        self.login('user2', '123')
        orig_data = dict(action="get_permissions")
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('admin' not in data['permissions'])

    def test_create_election(self):
        # check no election is listed as requested
        data = self.getAndParse('agora/1/requested_elections/', code=HTTP_OK)
        self.assertEqual(len(data['objects']), 0)

        self.login('user1', '123')
        # user1 creates an election, but remains in requested status as it's not
        # an admin
        data = self.postAndParse('agora/1/action/', data=self.base_election_data,
            code=HTTP_OK, content_type='application/json')

        orig_data_compare = dict(
            pretty_name=self.base_election_data['pretty_name'],
            description=self.base_election_data['description'],
            is_vote_secret=self.base_election_data['is_vote_secret'],
        )

        self.assertTrue('id' in data)
        self.assertDictContains(data, orig_data_compare)

        self.assertTrue('is_approved' in data)
        self.assertEquals(data['is_approved'], False)
        election_id = data['id']

        # check election is listed as requested
        data = self.getAndParse('agora/1/requested_elections/', code=HTTP_OK)
        self.assertEqual(len(data['objects']), 1)
        self.assertEqual(data['objects'][0]['id'], election_id)

        # save the current number of this agora's elections
        data = self.getAndParse('agora/1/all_elections/', code=HTTP_OK)
        num_elections = len(data['objects'])

        # now create an election as an admin user, that should automatically be
        # approved
        self.login('david', 'david')
        data = self.postAndParse('agora/1/action/', data=self.base_election_data,
            code=HTTP_OK, content_type='application/json')
        self.assertTrue('id' in data)
        self.assertTrue('is_approved' in data)
        self.assertEquals(data['is_approved'], True)

        # number of approved election remains the same
        data = self.getAndParse('agora/1/requested_elections/', code=HTTP_OK)
        self.assertEqual(len(data['objects']), 1)

        # but all elections contains it, there's a new one =)
        data = self.getAndParse('agora/1/all_elections/', code=HTTP_OK)
        self.assertEqual(len(data['objects']), num_elections + 1)

    def test_delegate_vote(self):
        # david delegates into user1, which has userid 1
        self.login('david', 'david')
        orig_data = dict(action='delegate_vote', user_id=1)
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')
        self.assertEqual(data["is_public"], True)
        self.assertEqual(data["is_direct"], False)
        self.assertEqual(data["is_counted"], True)
        self.assertEqual(data["reason"], '')
        self.assertEqual(data["invalidated_at_date"], None)
        self.assertEqual(data["public_data"]['a'], 'delegated-vote')
        self.assertEqual(data["public_data"]['answers'], [{'a': 'plaintext-delegate', 'choices': [{'username': 'user1', 'user_name': 'Juana Molero', 'user_id': 1}]}])
        delegate_vote_id = data['id']

        # admin creates a new election
        data = self.postAndParse('agora/1/action/', data=self.base_election_data,
            code=HTTP_OK, content_type='application/json')
        election_id = data['id']

        # admin starts the election
        orig_data = dict(action='start')
        data = self.postAndParse('election/%d/action/' % election_id,
            data=orig_data, code=HTTP_OK, content_type='application/json')

        # david delegated vote should already be there in delegated_votes,
        # even though user1 didn't vote yet
        data = self.getAndParse('election/%d/delegated_votes/' %  election_id,
            code=HTTP_OK)
        self.assertEqual(len(data['objects']), 1)
        self.assertEqual(data['objects'][0]['id'], delegate_vote_id)

        # david cancel his vote delegation
        orig_data = dict(action='cancel_vote_delegation')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # his delegated vote doesn't appear in election delegated votes, because
        # it was invalidated
        data = self.getAndParse('election/%d/delegated_votes/' %  election_id,
            code=HTTP_OK)
        self.assertEqual(len(data['objects']), 0)

        # david tries again to cancel his vote delegation - error, vote is not
        # currently delegated
        orig_data = dict(action='cancel_vote_delegation')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_BAD_REQUEST, content_type='application/json')

        # david tries to delegate into an inexistant user - error
        # david cancel his vote delegation
        orig_data = dict(action='delegate_vote', user_id=13232)
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_NOT_FOUND, content_type='application/json')

        # david tries to delegate without specifying the user id - error
        orig_data = dict(action='delegate_vote')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_BAD_REQUEST, content_type='application/json')

        # user1 tries to delegate his vote - error, not an agora member
        self.login('user1', '123')
        orig_data = dict(action='delegate_vote', user_id=2)
        data = self.post('agora/1/action/', data=orig_data,
            code=HTTP_FORBIDDEN, content_type='application/json')

        # user1 joins the agora
        orig_data = dict(action='join')
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_OK, content_type='application/json')

        # user1 tries to delegate into himself - error, you can't do that
        orig_data = dict(action='delegate_vote', user_id=1)
        data = self.postAndParse('agora/1/action/', data=orig_data,
            code=HTTP_BAD_REQUEST, content_type='application/json')
