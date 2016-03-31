from __future__ import unicode_literals
import random
import copy
import sys

from django import forms as django_forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .base import BaseVotingSystem, BaseTally
from agora_site.misc.utils import *

class BaseSTV(BaseVotingSystem):
    '''
    Defines the helper functions that allows agora to manage an OpenSTV-based
    STV voting system.
    '''

    @staticmethod
    def get_id():
        '''
        Returns the identifier of the voting system, used internally to
        discriminate  the voting system used in an election
        '''
        return 'BASE-STV'

    @staticmethod
    def get_description():
        return _('Multi-seat ranked voting - STV (Single Transferable Vote)')

    @staticmethod
    def create_tally(election, question_num):
        '''
        Create object that helps to compute the tally
        '''
        return BaseSTVTally(election, question_num)

    @staticmethod
    def get_question_field(election, question):
        '''
        Creates a voting field that can be used to answer a question in a ballot
        '''
        answers = [(answer['value'], answer['value'])
            for answer in question['answers']]
        random.shuffle(answers)

        return BaseSTVField(label=question['question'],
            choices=answers, required=True, election=election, question=question)

    @staticmethod
    def validate_question(question):
        '''
        Validates the value of a given question in an election
        '''
        error = django_forms.ValidationError(_('Invalid questions format'))

        if question['question'].strip() != clean_html(question['question'], True):
            raise error

        if 'num_seats' not in question or\
            not isinstance(question['num_seats'], int) or\
            question['num_seats'] < 1:
            raise error

        if question['a'] != 'ballot/question' or\
            not isinstance(question['min'], int) or question['min'] < 0 or\
            not isinstance(question['max'], int) or question['max'] < 1 or\
            question['min'] > question['max'] or\
            not isinstance(question['randomize_answer_order'], bool):
            raise error

        # check there are at least 2 possible answers
        if not isinstance(question['answers'], list) or\
            len(question['answers']) < 2 or\
            len(question['answers']) < question['num_seats'] or\
            len(question['answers']) > 100:
            raise error

        # check each answer
        answer_values = []
        for answer in question['answers']:
            if not isinstance(answer, dict):
                raise error

            # check it contains the valid elements
            if not list_contains_all(['a', 'value', 'url', 'details'],
                answer.keys()):
                raise error

            for el in ['a', 'value', 'url', 'details']:
                if not (isinstance(answer[el], unicode) or\
                    isinstance(answer[el], str)) or\
                    len(answer[el]) > 500:
                    raise error

            if answer['a'] != 'ballot/answer' or\
                not (
                    isinstance(answer['value'], unicode) or\
                    isinstance(answer['value'], str)
                ) or len(answer['value']) < 1:
                raise error

            if answer['value'] in answer_values:
                raise error

            if answer['value'].strip() != clean_html(answer['value'], True).replace("\n", ""):
                raise error
            answer_values.append(answer['value'])


class BaseSTVField(JSONFormField):
    '''
    A field that returns a valid answer text
    '''
    election = None

    def __init__(self, choices, election, question, *args, **kwargs):
        self.election = election
        self.question = question
        return super(BaseSTVField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """
        Wraps the choice field the proper way
        """
        error = django_forms.ValidationError(_('Invalid answer format'))

        if not isinstance(value, list):
            raise error

        # check for repeated answers
        if len(value) != len(set(value)):
            raise error

        if len(value) < self.question['min'] or len(value) > self.question['max']:
            raise error

        # find question in election
        question = None
        for q in self.election.questions:
            if q['question'] == self.label:
                question = q

        # gather possible answers
        possible_answers = [answer['value'] for answer in question['answers']]

        # check the answers provided are valid
        for i in value:
            if i not in possible_answers:
                raise error

        # NOTE: in the future, when encryption support is added, this will be
        # handled differently, probably in a more generic way so that
        # BaseSTVField doesn't know anything about plaintext or encryption.
        if len(value) > 0:
            clean_value = super(BaseSTVField, self).clean(value)
            return {
                "a": "plaintext-answer",
                "choices": clean_value,
            }
        else:
            return {
                "a": "plaintext-answer",
                "choices": [],
            }

class BaseSTVTally(BaseTally):
    '''
    Class oser to tally an election
    '''
    ballots_file = None
    ballots_path = ""

    # list containing the current list of ballots.
    # In each iteration this list is modified. For efficiency, ballots with the
    # same ordered choices are grouped. The format of each item in this list is
    # the following:
    #
    #{
        #'votes': 12, # number of ballots with this selection of choices
        #'answers': [2, 1, 4] # list of ids of the choices
    #}
    ballots = []

    # dict that has as keys the possible answer['value'], and as value the id
    # of each answer. 
    # Used because internally we store the answers by id with a number to speed
    # things up.
    answer_to_ids_dict = dict()
    num_seats = -1

    # openstv options
    method_name = "MeekSTV"
    strong_tie_break_method = None # None means default
    weak_tie_break_method = None # None means default
    digits_precision = None # None means default

    # report object
    report = None

    def init(self):
        import os
        import uuid
        self.ballots_path = os.path.join(settings.MEDIA_ROOT, 'elections',
            (str(uuid.uuid4()) + '.blt'))
        self.ballots = []
        self.answer_to_ids_dict = dict()

    def pre_tally(self, result):
        '''
        Function called once before the tally begins
        '''
        import codecs
        self.ballots_file = codecs.open(self.ballots_path, encoding='utf-8', mode='w')

        question = result[self.question_num]
        self.num_seats = question['num_seats']

        # fill answer to dict
        i = 1
        for answer in question['answers']:
            self.answer_to_ids_dict[answer['value']] = i
            i += 1

        # write the header of the BLT File 
        # See format here: https://code.google.com/p/droop/wiki/BltFileFormat
        self.ballots_file.write('%d %d\n' % (len(question['answers']), question['num_seats']))

    def answer2id(self, answer):
        '''
        Converts the answer to an id. 
        @return the id or -1 if not found
        '''
        return self.answer_to_ids_dict.get(answer, -1)

    def find_ballot(self, answers):
        '''
        Find a ballot with the same answers as the one given in self.ballots. 
        Returns the ballot or None if not found.
        '''
        for ballot in self.ballots:
            if ballot['answers'] == answers:
                return ballot

        return None

    def add_vote(self, voter_answers, result, is_delegated):
        '''
        Add to the count a vote from a voter
        '''
        answers = [self.answer2id(a) for a in voter_answers[self.question_num]['choices']]

        # we got ourselves an invalid vote, don't count it
        if -1 in answers:
            return

        ballot = self.find_ballot(answers)
        # if ballot found, increment the count. Else, create a ballot and add it
        if ballot:
            ballot['votes'] += 1
        else:
            self.ballots.append(dict(votes=1, answers=answers))

    def finish_writing_ballots_file(self, result):
        # write the ballots
        question = result[self.question_num]
        for ballot in self.ballots:
            self.ballots_file.write('%d %s 0\n' % (ballot['votes'],
                ' '.join([str(a) for a in ballot['answers']])))
        self.ballots_file.write('0\n')

        # write the candidates
        for answer in question['answers']:
            name = answer['value']
            name.encode('utf-8')
            ans = u'"%s"\n' % name
            self.ballots_file.write(ans)

        q = '"%s"\n' % question['question'].replace("\n", "").replace("\"", "")
        q.encode('utf-8')
        self.ballots_file.write(q)
        self.ballots_file.close()
        self.election.extra_data['ballots_path'] = self.ballots_path
        self.election.save()

    def perform_tally(self):
        '''
        Actually calls to openstv to perform the tally
        '''
        from openstv.ballots import Ballots
        from openstv.plugins import getMethodPlugins

        # get voting and report methods
        methods = getMethodPlugins("byName", exclude0=False)

        # generate ballots
        dirtyBallots = Ballots()
        dirtyBallots.loadKnown(self.ballots_path, exclude0=False)
        dirtyBallots.numSeats = self.num_seats
        cleanBallots = dirtyBallots.getCleanBallots()

        # create and configure election
        e = methods[self.method_name](cleanBallots)

        if self.strong_tie_break_method is not None:
            e.strongTieBreakMethod = self.strong_tie_break_method

        if self.weak_tie_break_method is not None:
            e.weakTieBreakMethod = self.weak_tie_break_method

        if self.digits_precision is not None:
            e.prec = self.digits_precision

        # run election and generate the report
        e.runElection()

        # generate report
        from .json_report import JsonReport
        self.report = JsonReport(e)
        self.report.generateReport()

    def fill_results(self, result):
        # fill result
        json_report = self.report.json
        last_iteration = json_report['iterations'][-1]

        question = result[self.question_num]
        question['total_votes'] = json_report['ballots_count']
        question['dirty_votes'] = json_report['dirty_ballots_count'] - json_report['ballots_count']
        json_report['winners'] = [winner.decode('utf-8') for winner in json_report['winners']]
        question['winners'] = json_report['winners']

        i = 1
        for answer in question['answers']:
            name = answer['value']
            name.encode('utf-8')
            it_answer = last_iteration['candidates'][i - 1]
            answer['elected'] = ('won' in it_answer['status'])

            if answer['elected']:
                answer['seat_number'] = json_report['winners'].index(name) + 1
            else:
                answer['seat_number'] = 0
            i += 1


    def post_tally(self, result):
        '''
        Once all votes have been added, this function actually save them to
        disk and then calls openstv to perform the tally
        '''
        self.finish_writing_ballots_file(result)
        self.perform_tally()
        self.fill_results(result)

    def get_log(self):
        '''
        Returns the tally log. Called after post_tally()
        '''
        return self.report.json
