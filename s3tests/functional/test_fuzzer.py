import nose
import random
import string
import yaml

from s3tests.fuzz_headers import *

from nose.tools import eq_ as eq
from nose.plugins.attrib import attr

from .utils import assert_raises

_decision_graph = {}

def check_access_denied(fn, *args, **kwargs):
    e = assert_raises(boto.exception.S3ResponseError, fn, *args, **kwargs)
    eq(e.status, 403)
    eq(e.reason, 'Forbidden')
    eq(e.error_code, 'AccessDenied')


def build_graph():
    graph = {}
    graph['start'] = {
        'set': {},
        'choices': ['node2']
    }
    graph['leaf'] = {
        'set': {
            'key1': 'value1',
            'key2': 'value2'
        },
        'choices': []
    }
    graph['node1'] = {
        'set': {
            'key3': 'value3'
        },
        'choices': ['leaf']
    }
    graph['node2'] = {
        'set': {
            'randkey': 'value-{random 10-15 printable}',
            'path': '/{bucket_readable}',
            'indirect_key1': '{key1}'
        },
        'choices': ['leaf']
    }
    graph['bad_node'] = {
        'set': {
            'key1': 'value1'
        },
        'choices': ['leaf']
    }
    return graph


def test_load_graph():
    graph_file = open('request_decision_graph.yml', 'r')
    graph = yaml.safe_load(graph_file)
    graph['start']


def test_descend_leaf_node():
    graph = build_graph()
    prng = random.Random(1)
    decision = descend_graph(graph, 'leaf', prng)

    eq(decision['key1'], 'value1')
    eq(decision['key2'], 'value2')
    e = assert_raises(KeyError, lambda x: decision[x], 'key3')


def test_descend_node():
    graph = build_graph()
    prng = random.Random(1)
    decision = descend_graph(graph, 'node1', prng)

    eq(decision['key1'], 'value1')
    eq(decision['key2'], 'value2')
    eq(decision['key3'], 'value3')


def test_descend_bad_node():
    graph = build_graph()
    prng = random.Random(1)
    assert_raises(KeyError, descend_graph, graph, 'bad_node', prng)


def test_SpecialVariables_dict():
    prng = random.Random(1)
    testdict = {'foo': 'bar'}
    tester = SpecialVariables(testdict, prng)

    eq(tester['foo'], 'bar')
    eq(tester['random 10-15 printable'], '[/pNI$;92@') #FIXME: how should I test pseudorandom content?

def test_assemble_decision():
    graph = build_graph()
    prng = random.Random(1)
    decision = assemble_decision(graph, prng)

    eq(decision['key1'], 'value1')
    eq(decision['key2'], 'value2')
    eq(decision['randkey'], 'value-{random 10-15 printable}')
    eq(decision['indirect_key1'], '{key1}')
    eq(decision['path'], '/{bucket_readable}')
    assert_raises(KeyError, lambda x: decision[x], 'key3')

def test_expand_decision():
    graph = build_graph()
    prng = random.Random(1)

    decision = assemble_decision(graph, prng)
    decision.update({'bucket_readable': 'my-readable-bucket'})

    request = expand_decision(decision, prng)

    eq(request['key1'], 'value1')
    eq(request['indirect_key1'], 'value1')
    eq(request['path'], '/my-readable-bucket')
    eq(request['randkey'], 'value-?') #FIXME: again, how to handle the pseudorandom content?
    assert_raises(KeyError, lambda x: decision[x], 'key3')

