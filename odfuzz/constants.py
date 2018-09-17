"""This module contains global constants."""

FUZZER_LOGS_NAME = 'logs'
STATS_LOGS_NAME = 'stats_overall'
FILTER_LOGS_NAME = 'stats_filter'
DATA_RESPONSES_NAME = 'data_responses'
DATA_RESPONSES_PLOT_NAME = 'responses_plot.html'
RUNTIME_FILE_NAME = 'runtime_info.txt'
LOGGING_CONFIG_PATH = 'config/logging/logging.conf'
CERTIFICATE_PATH = 'config/security/ca_sap_root_base64.crt'
FUZZER_CONFIG_PATH = 'config/fuzzer/fuzzer.ini'
CONFIG_SECTION = 'default'

# this set of constants must be equal to the corresponding
# logger keys defined in the CONFIG_PATH
FUZZER_LOGGER = 'fuzzer'
STATS_LOGGER = 'stats'
FILTER_LOGGER = 'filter'

MONGODB_NAME = 'odfuzz'
ACCESS_PROTOCOL = 'https://'

ENV_USERNAME = 'SAP_USERNAME'
ENV_PASSWORD = 'SAP_PASSWORD'

EXCLUDE = 'Exclude'
INCLUDE = 'Include'
EXPAND = '$expand'
ORDERBY = '$orderby'
TOP = '$top'
SKIP = '$skip'
FILTER = '$filter'
SEARCH = 'search'
GLOBAL_ENTITY = '$E_ALL$'
GLOBAL_FUNCTION = '$F_ALL$'
GLOBAL_PROPRTY = '$P_ALL$'
FORBID_OPTION = '$FORBID$'
DRAFT_OBJECTS = '$DRAFT$'
NAV_PROPRTY = '$NAV_PROP$'

QUERY_OPTIONS = [FILTER, ORDERBY, TOP, SKIP, EXPAND, SEARCH]
SINGLE_ENTITY_ALLOWED_OPTIONS = [FILTER, EXPAND]

STRING_FUNC_PROB = 0.70
MATH_FUNC_PROB = 0.15
DATE_FUNC_PROB = 0.15
FUNCTION_WEIGHT = 0.3
SINGLE_VALUE_PROB = 0.2
SINGLE_ENTITY_PROB = 0.05

SEARCH_MAX_LEN = 20
FUZZY_SEARCH_WILDCARD_PROB = 0.2
FUZZY_SEARCH_WITHOUT = 0.2
FUZZY_SEARCH_OR_PROB = 0.2
FUZZY_SEARCH_EQUAL_PROB = 0.2
MAX_FUZZY_SEARCH_ORS = 3

LOGICAL_OPERATORS = {'and': 0.5, 'or': 0.5}
BOOLEAN_OPERATORS = {'eq': 0.5, 'ne': 0.5}
INTERVAL_OPERATORS = {'le': 0.5, 'ge': 0.5}
EXPRESSION_OPERATORS = {'eq': 0.3, 'ne': 0.3, 'gt': 0.1, 'ge': 0.1, 'lt': 0.1, 'le': 0.1}
SEARCH_WILDCARDS = ['*', '%']

FILTER_CROSS_PROBABILITY = 0.8
EMPTY_ENTITY_PROB = 0.001
KEY_VALUES_MUTATION_PROB = 0.05
ASSOCIATED_ENTITY_PROB = 0.5
RECURSION_LIMIT = 3

STRING_THRESHOLD = 200
ITERATIONS_THRESHOLD = 30
CONTENT_LEN_SIZE = 50000
INT_MAX = 2147483647

FILTER_PARTS_NUM = 2
ORDERBY_MAX_PROPS = 3

SCORE_EPS = 200
ELITE_PROB = 0.7
FILTER_DEL_PROB = 0.1
ORDERBY_DEL_PROB = 0.1
OPTION_DEL_PROB = 0.1
MAX_MULTI_VALUES = 3
MAX_EXPAND_VALUES = 3
FILTER_SAMPLE_SIZE = 30
TOP_ENTITIES = 20

CSV = 'StatusCode;ErrorCode;ErrorMessage;EntitySet;AccessibleSet;AccessibleKeys;Property;orderby;top;skip;filter;expand;search'
CSV_FILTER = 'StatusCode;ErrorCode;ErrorMessage;EntitySet;Property;logical;operator;function;operand'

INFINITY_TIMEOUT = -1
YEAR_IN_SECONDS = 31622400
REQUEST_TIMEOUT = 600
RETRY_TIMEOUT = 100

HEX_BINARY = 'ABCDEFabcdef0123456789'
BASE_CHARSET = 'abcdefghijklmnopqrstuvxyzABCDEFGHIJKLMNOPQRSTUVXYZ0123456789~!$@^*()_+-–—=' \
               '[]|:<>.‰¨œƒ…†‡Œ‘’´`“”•™¡¢£¤¥¦§©ª«¬®¯°±²³µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍ' \
               'ÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ{} '
