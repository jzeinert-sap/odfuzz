"""This module contains core parts of the fuzzer and additional handler classes."""

import random
import time
import os
import sys
import uuid
import requests
import pymongo

from gevent.pool import Pool

from odfuzz.entities import Builder, FilterOptionBuilder, Option
from odfuzz.restrictions import RestrictionsGroup
from odfuzz.exceptions import DispatcherError
from odfuzz.constants import ENV_USERNAME, ENV_PASSWORD, MONGODB_NAME, SEED_POPULATION, \
    MONGODB_COLLECTION, FILTER, POOL_SIZE, STRING_THRESHOLD, DEATH_CHANCE, SCORE_EPS, \
    SELECTION_THRESHOLD, PARTS_NUM, ITERATIONS_THRESHOLD


class Manager(object):
    """A class for managing the fuzzer runtime."""

    def __init__(self, arguments):
        self._dispatcher = Dispatcher(arguments.service)
        self._async = getattr(arguments, 'async')

        restrictions_file = getattr(arguments, 'restr')
        if restrictions_file:
            self._restrictions = RestrictionsGroup(restrictions_file)
        else:
            self._restrictions = None

    def start(self):
        builder = Builder(self._dispatcher, self._restrictions)
        entities = builder.build()

        fuzzer = Fuzzer(self._dispatcher, entities, async=self._async)
        fuzzer.run()


class Fuzzer(object):
    """A main class that initiates a fuzzing process."""

    def __init__(self, dispatcher, entities, **kwargs):
        self._dispatcher = dispatcher
        self._entities = entities
        self._mongodb = MongoClient()
        self._analyzer = Analyzer(self._mongodb)
        self._selector = Selector(self._mongodb, self._entities)

        self._async = kwargs.get('async')
        if self._async:
            self._crossover = self._crossover_multiple
            self._generate = self._generate_multiple
        else:
            self._crossover = self._crossover_single
            self._generate = self._generate_single

        self._tests_num = 0
        self._fails_num = 0

    def run(self):
        time_seed = time.time()
        random.seed(time_seed)

        self.seed_population()
        self._selector.score_average = self._mongodb.overall_score() / self._mongodb.total_queries()
        self.evolve_population()

    def seed_population(self):
        for queryable in self._entities.all():
            seed_range = len(queryable.entity_set.entity_type.proprties()) * SEED_POPULATION
            if self._async:
                seed_range = round(seed_range / POOL_SIZE)
            for _ in range(seed_range):
                queries = self._generate(queryable)
                self._evaluate_queries(queries)
                self._save_to_database(queries)
                self._print_tests_num()

    def evolve_population(self):
        while True:
            selection = self._selector.select()
            old_tests_num = self._tests_num
            if selection.crossable:
                queries = self._crossover(selection.crossable, selection.queryable.entity_set.name)
            else:
                queries = self._generate(selection.queryable)
            self._evaluate_queries(queries)
            self._save_to_database(queries)
            generated_tests = self._tests_num - old_tests_num
            self._slay_weak_individuals(selection.score_average, generated_tests)
            self._print_tests_num()

    def _generate_multiple(self, queryable):
        queries = []
        for _ in range(POOL_SIZE):
            query = self._generate_query(queryable)
            if query:
                queries.append(query)
        if queries:
            self._get_multiple_responses(queries)
        return queries

    def _generate_single(self, queryable):
        query = self._generate_query(queryable)
        if query:
            self._get_single_response(query)
        return [query]

    def _generate_query(self, queryable):
        query = Query(queryable.entity_set.name)
        try:
            option = queryable.query_option(FILTER)
        except KeyError:
            return None

        generated_option = option.generate()
        query.add_option(FILTER, generated_option.data)
        query.query_string = query.entity_name + '?' + option.name \
                                               + '=' + generated_option.option_string
        self._tests_num += 1
        return query

    def _crossover_multiple(self, crossable_selection, entity_set_name):
        children = []
        for _ in range(POOL_SIZE):
            query1, query2 = crossable_selection
            offspring = self._crossover_queries(query1, query2, entity_set_name)
            if offspring:
                children.append(offspring)
        if children:
            self._get_multiple_responses(children)
        return children

    def _crossover_single(self, crossable_selection, entity_set_name):
        query1, query2 = crossable_selection
        query = self._crossover_queries(query1, query2, entity_set_name)
        self._get_single_response(query)
        return [query]

    def _crossover_queries(self, query1, query2, entity_set_name):
        offspring = self._mate(query1, query2)
        query = Query(entity_set_name)
        query.add_option(FILTER, offspring)
        option = Option(offspring['logicals'], offspring['parts'], offspring['groups'])
        option_string = FilterOptionBuilder(option).build()
        query.query_string = query.entity_name + '?$filter=' \
                             + option_string
        self._tests_num += 1
        return query

    def _mate(self, query1, query2):
        filter_option1 = query1['filter']
        filter_option2 = query2['filter']

        part_to_replace = random.choice(filter_option1['parts'])
        replacing_part = random.choice(filter_option2['parts'])

        part_to_replace['name'] = replacing_part['name']
        part_to_replace['operator'] = replacing_part['operator']
        part_to_replace['operand'] = replacing_part['operand']

        return filter_option1

    def _get_multiple_responses(self, queries):
        responses = []
        pool = Pool(POOL_SIZE)
        for query in queries:
            responses.append(pool.spawn(self._get_single_response, query))
        pool.join()

    def _get_single_response(self, query):
        query.response = self._dispatcher.get(query.query_string)
        if query.response.status_code != 200:
            self._fails_num += 1

    def _evaluate_queries(self, queries):
        for query in queries:
            if query:
                self._analyzer.analyze(query)

    def _save_to_database(self, queries):
        for query in queries:
            if query:
                self._mongodb.save_document(query.dictionary)

    def _slay_weak_individuals(self, score_average, number):
        self._mongodb.remove_weak_queries(score_average, number)

    def _print_tests_num(self):
        sys.stdout.write('Generated tests: {} | Failed tests: {} \r'
                         .format(self._tests_num, self._fails_num))
        sys.stdout.flush()


class Selector(object):
    def __init__(self, mongodb, entities):
        self._mongodb = mongodb
        self._score_average = 0
        self._passed_iterations = 0
        self._entities = entities

    @property
    def score_average(self):
        return self._score_average

    @score_average.setter
    def score_average(self, value):
        self._score_average = value

    def select(self):
        self._compute_score_average()
        if self._is_score_stagnating():
            selection = Selection(None, random.choice(list(self._entities.all())),
                                  self._score_average)
        else:
            queryable = random.choice(list(self._entities.all()))
            crossable = self._get_crossable(queryable)
            while not crossable or len(crossable) == 1:
                queryable = random.choice(list(self._entities.all()))
                crossable = self._get_crossable(queryable)
            selection = Selection(crossable, queryable, self._score_average)
        self._passed_iterations += 1

        return selection

    def _is_score_stagnating(self):
        if self._passed_iterations > ITERATIONS_THRESHOLD:
            self._passed_iterations = 0
            current_average = self._mongodb.overall_score() / self._mongodb.total_queries()
            old_average = self._score_average
            self._score_average = current_average
            if abs(old_average - current_average) < SCORE_EPS:
                return True
        return False

    def _compute_score_average(self):
        pass

    def _get_crossable(self, queryable):
        queries_pair = None
        for _ in range(SELECTION_THRESHOLD):
            queries_pair = self._mongodb.find_similar_queries('500', queryable.entity_set.name)
            if not queries_pair:
                queries_pair = self._mongodb.find_similar_queries('200', queryable.entity_set.name)
                if not queries_pair:
                    continue
            if len(queries_pair) == 2:
                break
        return queries_pair


class Selection(object):
    def __init__(self, crossable, queryable, score_average):
        self._crossable = crossable
        self._queryable = queryable
        self._score_average = score_average

    @property
    def crossable(self):
        return self._crossable

    @property
    def queryable(self):
        return self._queryable

    @property
    def score_average(self):
        return self._score_average


class Analyzer(object):
    """An analyzer for analyzing generated queries."""

    def __init__(self, mongodb):
        self._mongodb = mongodb
        self._population_score = 0

    def analyze(self, query):
        new_score = FitnessEvaluator.evaluate(query)
        query.score = new_score

        self._update_population_score(new_score)
        query = self._mongodb.query_by_id(query.query_id)
        if query and 'predecessors' in query:
            if not self._has_offspring_good_score(query['predecessors'], new_score):
                if random.random() < DEATH_CHANCE:
                    return AnalysisInfo(new_score, True, self._population_score)
        return AnalysisInfo(new_score, False, self._population_score)

    def _has_offspring_good_score(self, predecessors_id, new_score):
        for predecessor_id in predecessors_id:
            if self._mongodb.query_by_id(predecessor_id)['score'] <= new_score:
                return True
        return False

    def _update_population_score(self, query_score):
        if self._population_score == 0:
            self._population_score = self._mongodb.overall_score()
        else:
            self._population_score += query_score


class AnalysisInfo(object):
    """A set of basic information about performed analysis."""

    def __init__(self, score, killable, population_score):
        self._score = score
        self._killable = killable
        self._population_score = population_score

    @property
    def score(self):
        return self._score

    @property
    def killable(self):
        return self._killable

    @property
    def population_score(self):
        return self._population_score


class FitnessEvaluator(object):
    """A group of heuristic functions."""

    @staticmethod
    def evaluate(query):
        total_score = 0
        keys_len = sum(len(option_name) for option_name in query.options.keys())
        query_len = len(query.query_string) - len(query.entity_name) - keys_len
        total_score += FitnessEvaluator.eval_string_length(query_len)
        total_score += FitnessEvaluator.eval_http_status_code(query.response.status_code)
        total_score += FitnessEvaluator.eval_http_response_time(query.response.elapsed
                                                                .total_seconds())
        return total_score

    @staticmethod
    def eval_http_status_code(status_code):
        if status_code == 500:
            return 100
        else:
            return 0

    @staticmethod
    def eval_http_response_time(total_seconds):
        if total_seconds < 2:
            return 0
        elif total_seconds < 10:
            return 1
        elif total_seconds < 20:
            return 2
        else:
            return 5

    @staticmethod
    def eval_string_length(string_length):
        return round(STRING_THRESHOLD / string_length)


class SAPErrors(object):
    """A container of all types of errors produced by the SAP systems."""
    pass


class Query(object):
    """A wrapper of a generated query."""

    def __init__(self, entity_name):
        self._entity_name = entity_name
        self._options = {}
        self._query_string = ''
        self._dict = {}
        self._score = {}
        self._predecessors = []
        self._response = None
        self._id = str(uuid.UUID(int=random.getrandbits(128), version=4))

    @property
    def entity_name(self):
        return self._entity_name

    @property
    def options(self):
        return self._options

    @property
    def query_string(self):
        return self._query_string

    @property
    def response(self):
        return self._response

    @property
    def dictionary(self):
        if not self._dict:
            self._create_dict()
        return self._dict

    @property
    def score(self):
        return self._score

    @property
    def query_id(self):
        return self._id

    @property
    def predecessors(self):
        return self._predecessors

    @query_string.setter
    def query_string(self, value):
        self._query_string = value

    @response.setter
    def response(self, value):
        self._response = value

    @score.setter
    def score(self, value):
        self._score = value

    def add_option(self, name, option):
        self._options[name] = option

    def add_predecessor(self, predecessor_id):
        self._predecessors.append(predecessor_id)

    def _create_dict(self):
        self._dict['HTTP'] = str(self._response.status_code)
        self._dict['ErrorCode'] = getattr(self._response, 'error_code', None)
        self._dict['ErrorMessage'] = getattr(self._response, 'error_message', None)
        self._dict['EntitySet'] = {'name': self._entity_name,
                                   'queries': [
                                       {'id': self._id,
                                        'predecessors': self._predecessors,
                                        'string': self._query_string,
                                        'score': self._score,
                                        'search': self._options.get('search'),
                                        'top': self._options.get('$top'),
                                        'skip': self._options.get('$skip'),
                                        'filter': self._options.get(FILTER)}
                                   ]}


class MongoClient(object):
    """A NoSQL database client."""

    def __init__(self):
        self._mongodb = pymongo.MongoClient()
        self._collection = self._mongodb[MONGODB_NAME][MONGODB_COLLECTION]

    def save_document(self, query_dict):
        was_inserted = self.insert_single_document(query_dict)
        if not was_inserted:
            self.update_single_document(query_dict)

    def insert_single_document(self, query_dict):
        cursor = self._collection.find({'EntitySet.name': query_dict['EntitySet']['name'],
                                        'ErrorCode': query_dict['ErrorCode']})
        if cursor.count() == 0:
            self._collection.insert_one(query_dict)
            return True
        return False

    def update_single_document(self, query_dict):
        entity_set_dict = query_dict['EntitySet']
        query = entity_set_dict['queries'][0]
        self._collection.update_one(
            {'$and': [
                {'EntitySet.name': entity_set_dict['name']},
                {'ErrorCode': query_dict['ErrorCode']},
                {'EntitySet.queries.string': {'$ne': query['string']}}
            ]},
            {'$push': {'EntitySet.queries': query}}
        )

    def query_by_id(self, query_id):
        cursor = self._collection.aggregate(
            [
                {'$project': {'Query': '$EntitySet.queries'}},
                {'$unwind': '$Query'},
                {'$match': {'Query.id': query_id}}
            ])

        cursor_list = list(cursor)
        if cursor_list:
            return cursor_list[0]
        return None

    def overall_score(self):
        cursor = self._collection.aggregate(
            [
                {'$project': {'EntityOverall': {'$sum': '$EntitySet.queries.score'}}},
                {'$group': {'_id': None, 'Overall': {'$sum': '$EntityOverall'}}}
            ])
        population_overall = list(cursor)[0]['Overall']
        return population_overall

    def total_queries(self):
        cursor = self._collection.aggregate(
            [
                {'$project': {'Query': '$EntitySet.queries'}},
                {'$unwind': '$Query'},
                {'$count': 'total'}
            ])
        queries_num = list(cursor)[0]['total']
        return queries_num

    def queries_sample(self, http_code, entity_set_name, sample_size):
        cursor = self._collection.aggregate(
            [
                {'$match': {'HTTP': http_code, 'EntitySet.name': entity_set_name}},
                {'$project': {'Query': '$EntitySet.queries'}},
                {'$unwind': '$Query'},
                {'$sample': {'size': sample_size}}
            ])
        queries = [query['Query'] for query in cursor]
        return queries

    def remove_weak_queries(self, score_average, number):
        print(score_average)
        cursor = self._collection.aggregate(
            [
               # {'$project': {'Query': '$EntitySet.queries'}},
               # {'$unwind': '$Query'},
               # {'$match': {'Query.score': {'$lt': score_average}}},
               # {'$limit': number},
                {'$project': {'Query': '$EntitySet.queries'}},
                {'$unwind': '$Query'},
                {'$match': {'Query.score': {'$lt': 5.521123123213123123213123}}},
                {'$limit': 1}

            ])
        ids_to_delete = []
        for query in cursor:
            ids_to_delete.append(query['Query']['id'])
        self._collection.update({}, {'$pull': {'EntitySet.queries': {'id': {'$in': ids_to_delete}}}},
                             multi=True)
        return len(ids_to_delete)

    def find_similar_queries(self, http_code, entity_set_name):
        cursor = self._collection.aggregate(
            [
                {'$match': {'HTTP': http_code, 'EntitySet.name': entity_set_name}},
                {'$project': {'Query': '$EntitySet.queries'}},
                {'$unwind': '$Query'},
                {'$match': {'$expr': {'$gte': [{'$size': '$Query.filter.parts'}, PARTS_NUM]}}},
                {'$sample': {'size': 2}}
            ])
        similar_queries = [query['Query'] for query in cursor]
        return similar_queries


class Dispatcher(object):
    """A dispatcher for sending HTTP requests to the particular OData service."""

    def __init__(self, service, sap_certificate=None):
        self._service = service.rstrip('/') + '/'
        self._sap_certificate = sap_certificate

        self._session = requests.Session()
        self._session.auth = (os.getenv(ENV_USERNAME), os.getenv(ENV_PASSWORD))
        self._session.verify = self._get_sap_certificate()

    @property
    def session(self):
        return self._session

    @property
    def service(self):
        return self._service

    def send(self, method, query, **kwargs):
        url = self._service + query
        try:
            response = self._session.request(method, url, **kwargs)
        except requests.exceptions.RequestException as requests_ex:
            raise DispatcherError('An exception was raised while sending HTTP {}: {}'
                                  .format(method, requests_ex))
        return response

    def get(self, query, **kwargs):
        return self.send('GET', query, **kwargs)

    def post(self, query, **kwargs):
        return self.send('POST', query, **kwargs)

    def _get_sap_certificate(self):
        if not self._sap_certificate:
            self_dir = os.path.dirname(__file__)
            candidate_path = os.path.join(self_dir, '../config/security/ca_sap_root_base64.crt')
            if not os.path.isfile(candidate_path):
                return None
            self._sap_certificate = candidate_path
        return self._sap_certificate
