from __future__ import division

import logging
from builtins import str
from builtins import range
from builtins import object
from past.utils import old_div
from requests.exceptions import RequestException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from uservoice.client import APIError, Unauthorized

PER_PAGE = 100

def retry_logger(fxn, attempt_number, elapsed_seconds):
    logging.info("Retrying {} (try #{}, {}s passed)".format(fxn.__name__, attempt_number, elapsed_seconds))

class Collection(object):
    RETRY_KWARGS = {
        'after': retry_logger,
        'reraise': True,
        'retry': retry_if_exception_type((APIError, RequestException)),
        'stop': stop_after_attempt(10),
        'wait': wait_exponential(multiplier=5, max=300)
    }

    def __init__(self, client, query, limit=2**60):
        self.client = client
        self.query = query
        self.limit = limit
        self.per_page = min(self.limit, PER_PAGE)
        self.pages = {}
        self.response_data = None
        self.index = -1

    def __len__(self):
        if not self.response_data:
            try:
                self[0]
            except IndexError:
                pass

        return min(self.response_data['total_records'], self.limit)

    @retry(**RETRY_KWARGS)
    def __getitem__(self, i):
        try:
            if i == 0 or (i > 0 and i < len(self)):
                return self.load_page(int(old_div(i,float(PER_PAGE))) + 1)[i % PER_PAGE]
            else:
                raise IndexError
        except Unauthorized as e:
            if self.client.login_email is None:
                self.client.login_as_owner()
            else:
                self.client.login_as(self.client.login_email)

            raise e


    def __iter__(self):
        return self

    def __next__(self):
        self.index += 1

        if self.index >= len(self):
            raise StopIteration

        return self[self.index]


    def load_page(self, i):
        if not i in self.pages:
            url = self.query
            if '?' in self.query:
                url += '&'
            else:
                url += '?'
            result = self.client.get(url + "per_page=" + str(self.per_page) + "&page=" + str(i))

            if 'response_data' in result:
                self.response_data = result.pop('response_data')
                if len(list(result.values())) > 0:
                    self.pages[i] = list(result.values())[0]
            else:
                raise uservoice.NotFound.new('The resource you requested is not a collection')
        return self.pages[i]
