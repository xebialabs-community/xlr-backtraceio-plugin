#
# Copyright 2019 XEBIALABS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import sys 
import json
from xlrelease.HttpRequest import HttpRequest
import urllib
import time
from functools import reduce

class BacktraceClient(object):
    def __init__(self, httpConnection, username=None, password=None):
        self.httpConnection = httpConnection
        if username is not None:
            self.httpConnection['username'] = username
        if password is not None:
            self.httpConnection['password'] = password
        params = {'url': httpConnection['url'], 'proxyHost': httpConnection['proxyHost'], 'proxyPort': httpConnection['proxyPort'] }
        self.httpRequest = HttpRequest(params)
        self.accessToken = self._getAuthToken()
        self.headers = {'Accept': 'application/json', 'Cookie': 'token=%s' % self.accessToken}
    
    @staticmethod
    def create_client(httpConnection, username=None, password=None):
        return BacktraceClient(httpConnection, username, password)

    def _getAuthToken(self):
        cred = {'username': self.httpConnection['username'], 'password': self.httpConnection['password']}	
        
        response = self.httpRequest.post('/api/login', body=urllib.urlencode(cred), contentType='application/x-www-form-urlencoded')
        
        if response.getStatus() == 200:
            token = json.loads(response.getResponse())
            print "Successfully logged in with username %s." % cred['username']
            return token['token']
        else:
            sys.exit("Getting token failed:\n\n%s\n\n" % (response.getResponse()))

    def query(self, universe, projectKey, projectVersion, threshold, environment=None):
        api_url = "/api/query?project=%s&universe=%s" % (projectKey, universe)
        # this filter searches for any timestamp and passes the right arguments so we get error count
        filter_str = '{"filter":[{"timestamp":[["at-least","1."],["at-most","%i."]]}],"group":["fingerprint;issues;state"],"fold":{"fingerprint":[["unique"]]}}' % time.time()
        filter_obj = json.loads(filter_str)

        if environment:
            filter_obj['filter'][0]["hostname"] = [["contains",environment]]

        response = self.httpRequest.post(api_url, json.dumps(filter_obj), contentType = 'application/json', headers=self.headers)

        print('Http Response code is %s.\r\n' % response.status)

        # check response status code, if is different than 200 exit with error code
        if response.status != 200:
            sys.exit("Error from server: [%s]." % response.response)

        errors = json.loads(response.response)['response']['values']

        # errors object looks like: [[u'resolved', [[0]], 12], [u'open', [[0]], 492], [u'in-progress', [[2]], 12]]
        errors_open_or_in_progress = list(filter(lambda x: x[0] == 'open' or x[0] == 'in-progress', errors))

        # errors_open_or_in_progress looks like: [[u'open', [[0]], 492], [u'in-progress', [[2]], 12]]
        number_of_errors_list = list(map(lambda x: x[2], errors_open_or_in_progress))

        total_errors_not_closed = 0
        if len(number_of_errors_list) > 0:
            # number_of_errors_list looks like: [492, 12]
            total_errors_not_closed = reduce((lambda x, y: x + y), number_of_errors_list)

        if (total_errors_not_closed > int(threshold)):
            sys.exit("More errors (%s) found than threshold (%s).\r\n" % (total_errors_not_closed, threshold))

        print("%s errors (under or equal to threshold of %s) found for project with key %s and version %s" % (total_errors_not_closed, threshold, projectKey, projectVersion))
