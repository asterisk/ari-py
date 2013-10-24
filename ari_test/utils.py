#!/usr/bin/env python

import httpretty
import os
import unittest
import urlparse
import ari
import requests


class AriTestCase(unittest.TestCase):
    """Base class for mock ARI server.
    """

    BASE_URL = "http://ari.py/ari"

    def setUp(self):
        """Setup httpretty; create ARI client.
        """
        super(AriTestCase, self).setUp()
        httpretty.enable()
        self.serve_api()
        self.uut = ari.connect('http://ari.py/', 'test', 'test')

    def tearDown(self):
        """Cleanup.
        """
        super(AriTestCase, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    @classmethod
    def build_url(cls, *args):
        """Build a URL, based off of BASE_URL, with the given args.

        >>> AriTestCase.build_url('foo', 'bar', 'bam', 'bang')
        'http://ari.py/ari/foo/bar/bam/bang'

        :param args: URL components
        :return: URL
        """
        url = cls.BASE_URL
        for arg in args:
            url = urlparse.urljoin(url + '/', arg)
        return url

    def serve_api(self):
        """Register all api-docs with httpretty to serve them for unit tests.
        """
        for filename in os.listdir('sample-api'):
            if filename.endswith('.json'):
                with open(os.path.join('sample-api', filename)) as fp:
                    body = fp.read()
                self.serve(httpretty.GET, 'api-docs', filename, body=body)

    def serve(self, method, *args, **kwargs):
        """Serve a single URL for current test.

        :param method: HTTP method. httpretty.{GET,PUT,POST,DELETE}.
        :param args: URL path segments.
        :param kwargs: See httpretty.register_uri()
        """
        url = self.build_url(*args)
        if kwargs.get('body') is None and 'status' not in kwargs:
            kwargs['status'] = requests.codes.no_content
        httpretty.register_uri(method, url,
                               content_type="application/json",
                               **kwargs)
