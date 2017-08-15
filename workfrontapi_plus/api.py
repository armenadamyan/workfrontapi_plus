"""
Copyright (c) 2017 Craig Lathrop & Roshan Bal

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

#  Original copyright notice from Workfront Version of this API
#
#  Copyright (c) 2010 AtTask, Inc.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
#  Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#  WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import requests
import math
import json
from workfrontapi_plus.objects.core_wf_object import WorkfrontObject, WorkfrontAPIException, StreamNotModifiedException, StreamClientNotSet
from wfconfig import WorkfrontConfig
# import WorkfrontObject

class Api(object):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'

    LOGIN_PATH = "/login"
    LOGOUT_PATH = "/logout"

    # OBJCODES = ObjCode()

    CORE_URL = "https://{subdomain}.{env}.workfront.com/attask/api/v{version}"

    def __init__(self, subdomain, env, api_version='7.0', api_key=None, session_id=None, user_id=None, debug=False,
                 test_mode=False):
        """
        Setup class
        
        :param subdomain: The sub domain for your account
        :param env: {'live', 'sandbox', or 'preview'} default 'sandbox'
        :param api_version: The full version number for the API. Example '7.0'. Default 7.0
        :param api_key: The API key for authentication. Default None.
        :param session_id: An optional session ID for authentication
        :param user_id: The ID of the authenticated user
        """
        self.subdomain = subdomain
        api_base_url = self.CORE_URL.format(subdomain=subdomain,
                                            env=env,
                                            version=api_version)

        self.api_base_url = api_base_url
        self.session_id = session_id
        self.user_id = user_id
        self.api_key = api_key
        self.debug = debug
        self.test_mode = test_mode
        self._max_bulk = 99
        self._max_results = 2000

        # These methods are set as class variables to enable easy re-assignment during unit testing.
        # These values are typically overwritten by the unit tests with a lambda function simulating the results
        # of the method.
        self._request = self._make_request
        self._count = self.count
        self._open_api_connection = self._p_open_api_connection



    @staticmethod
    def test_mode_make_request(*args):
        return args

    def login(self, username, password=None):
        """
        Login to Workfront using username and optionally password.
        
        This method will make a login _request and set the lession ID.
        
        If an API key is set the password is not needed. The resulting sessionID
        will allow you to act on behalf of a user.

        https://developers.workfront.com/api-docs/#Login

        :param username: The Workfront username, typically an email address
        :param password: The Workfront password
        :return: The results of the login.
        """
        params = {'username': username}
        if password:
            params['password'] = password

        data = self._request(self.LOGIN_PATH, params, self.GET)

        if 'sessionID' in data:
            self.session_id = data['sessionID']
            self.user_id = data['userID']
            # Just a short cut here. Return script looks for 2.
            return data
        else:
            return data

    def logout(self):
        """
        Logout method.

        Clears the class session_id and user_id fields.
        """
        self._request(self.LOGOUT_PATH, None, self.GET)
        self.session_id = None
        self.user_id = None

    def get_list(self, objcode, ids, fields=None):
        """
        Returns each object by id, similar to calling get for each id individually

        :param objcode: object type (i.e. 'PROJECT')
        :param ids: list of ids to lookup
        :param fields: list of field names to return for each object
        :return: Data from Workfront
        """
        path = '/{0}'.format(objcode)
        return self._request(path, {'ids': ','.join(ids)}, fields)

    def put(self, objcode, objid, params, fields=None):
        """
        Updates an existing object, returns the updated object.

        https://developers.workfront.com/api-docs/#PUT

        :param objcode: object type (i.e. 'PROJECT')
        :param objid: The ID of the object to act on
        :param params: A dict of parameters to filter on
        :param fields: List of field names to return for each object
        :return: Data from Workfront
        """
        path = '/{0}/{1}'.format(objcode, objid)
        return self._request(path, params, self.PUT, fields)

    def action(self, objcode, action, params, fields=None, objid=None):
        """
        Updates an existing object, returns the updated object
        :param objcode: object type (i.e. 'PROJECT')
        :param objid: Object ID to operate on
        :param action: action to execute
        :param params: A dict of parameters to filter on
        :param fields: A list of fields to return - Optional
        """
        if objid:
            path = '/{objcode}/{objid}'.format(objcode=objcode, objid=objid, action=action)
        else:  # for some bulk operations you don't want to pass an obj ID in
            path = '/{objcode}'.format(objcode=objcode, action=action)

        params['action'] = action

        return self._request(path, params, self.PUT, fields)

    @staticmethod
    def _bulk_segmenter(bulk_method, objs_per_loop, **kwargs):
        """
        Breaks a list of items up into chunks for processing.

        :param bulk_method: An instance of the method (self.bulk, self.bulk_delete, self.bulk_create)
        :param kwargs: The various parameters
        :return: The output of the update from API
        """
        output = []
        if 'updates' in kwargs:
            data = kwargs['updates']
            key = 'updates'
        else:
            data = kwargs['objids']
            key = 'objids'
        for i in range(0, len(data), objs_per_loop):

            sliced_update_list = list(data[i:i + objs_per_loop])
            kwargs[key] = sliced_update_list
            output += bulk_method(**kwargs)

        return output

    def get_max_update_obj_size(self, updates):
        """
        Gets the total len of the updates when converted to JSON.

        There appears to be a char limit of ~6800 when making a bulk request. This seems related to total
        char len only, not number of elements.

        This method checks the size of the JSON converted "updates" and calculates a safe self._max_bulk
        value.
        :param updates: A dict containing updates
        :return: A safe value for self._max_bulk
        """
        # Actual limit seems to be ~6894 but errors are seen sometime at numbers down to 5000. It's possible that
        # the problem is not related to overall char size, but is something to do with some other field length or
        # attempting to add or modify so many objects at once. This issue isn't well understood at the moment.
        api_char_limit = 3000
        updates_len = len(updates)
        json_len = len(json.dumps(updates))
        char_per_update_element = int(math.ceil(json_len/updates_len))
        safe_elements_per_loop = int(math.floor(api_char_limit / char_per_update_element))
        print('Safe number of update elements per loop is {0}'.format(safe_elements_per_loop))
        return safe_elements_per_loop if safe_elements_per_loop < self._max_bulk else self._max_bulk

    def bulk(self, objcode, updates, fields=None):
        """
        Makes bulk updates to existing objects

        :param objcode: object type (i.e. 'PROJECT')
        :param updates: A list of dicts contining the updates
        :param fields: A list of fields to return - Optional
        :return: The results of the _request as a list of updated objects
        """
        max_objs_per_loop = self.get_max_update_obj_size(updates)
        res = []
        if len(updates) > max_objs_per_loop:
            res = self._bulk_segmenter(self.bulk,
                                      objs_per_loop=max_objs_per_loop,
                                      objcode=objcode,
                                      updates=updates,
                                      fields=fields)
            return res
        path = '/{0}'.format(objcode)
        params = {'updates': json.dumps(updates)}

        return self._request(path, params, self.PUT, fields)

    def bulk_create(self, objcode, updates, fields=None):
        """
        Bulk creation of objects such as tasks, issues, other.

        This method differs from bulk in that it uses the POST operation, not PUT
        :param objcode: object type (i.e. 'PROJECT')
        :param updates: A list of dicts containing the updates
        :param fields: List of field names to return for each object
        :return: The results of the _request as a list of newly created objects
        """
        max_objs_per_loop = self.get_max_update_obj_size(updates)
        res = []
        if len(updates) > self._max_bulk:
            res = self._bulk_segmenter(self.bulk_create,
                                       objs_per_loop=max_objs_per_loop,
                                       objcode=objcode,
                                       updates=updates,
                                       fields=fields)
            return res
        path = '/{0}'.format(objcode)
        params = {'updates': json.dumps(updates)}
        return self._request(path, params, self.POST, fields)

    def post(self, objcode, params, fields=None):
        """
        Creates a new object, returns the new object

        https://developers.workfront.com/api-docs/#POST

        :param objcode: object type (i.e. 'PROJECT')
        :param params: A dict of parameters to filter on.
        :param fields: List of field names to return for each object.
        :return: The results of the updated object.
        """
        path = '/{0}'.format(objcode)
        return self._request(path, params, self.POST, fields)

    def get(self, objcode, objid, fields=None):
        """
        Lookup an object by id

        :param objcode: object type (i.e. 'PROJECT')
        :param objid: Object ID to operate on
        :param fields:
        :return: The requested object with requested fields
        """
        path = '/{0}/{1}'.format(objcode, objid)
        return self._request(path, None, self.GET, fields)

    def delete(self, objcode, objid, force=True):
        """
        Delete by object ID

        :param objcode: object type (i.e. 'PROJECT')
        :param objid: Object ID to operate on
        :param force: Force deletion of the object with relationships. For example
                      if a task is deleted with force "False" associated expenses will
                      not be removed.
        :return: The results of the deletion
        """
        path = '/{0}/{1}'.format(objcode, objid)
        return self._request(path, {'force': force}, self.DELETE)

    def bulk_delete(self, objcode, objids, force=True, atomic=True):
        """
        Delete by object ID

        :param objcode: object type (i.e. 'PROJECT')
        :param objids: A list of object IDs to be deleted
        :param force: True by default. Force deletion of the object with relationships. For example
                      if a task is deleted with force "False" associated expenses will
                      not be removed.
        :param atomic: True by default. Removes all objects at the same time. This is useful is situations where you might be deleting
                       a parent object with children in the same set of "ids". For example:

                       Task A
                            Task B
                            Task C

                       If in the above example you delete Task A, Task B and C will be deleted automatically. If you do
                       not specify atomic=True and the ID's for Task B and C are in the list of ID's to be deleted it
                       will throw an error as it will not be able to find those ID's.
        :return: The results of the deletion
        """
        res = []
        if len(objids) > self._max_bulk:
            res = self._bulk_segmenter(self.bulk_delete,
                                       objs_per_loop=self._max_bulk,
                                       objcode=objcode,
                                       objids=objids,
                                       force=True,
                                       atomic=True)
            return res
        path = '/{0}'.format(objcode)

        params = {"ID": objids, "force": force}
        if atomic:
            params['atomic'] = 'true'
        return self._request(path, params, self.DELETE)

    def search(self, objcode, params, fields=None, get_all=False, limit=None):
        """
        Search for objects against a given set of filters (params).

        :param objcode: Object code to search for.
        :param params:
        :param fields:
        :return:
        """
        path = '/{0}/search'.format(objcode)
        if get_all or limit:
            output = []
            first = 0
            count = self._count(objcode, params)
            if limit:
                count = count if count < limit else limit
                limit = self._max_results if limit > self._max_results else limit
            else:
                limit = self._max_results
            loop_count = int(math.ceil(count / self._max_results))
            params['$$LIMIT'] = limit
            for i in range(0, loop_count):
                if i == (loop_count - 1):
                    params['$$LIMIT'] = count - ((loop_count - 1) * limit)
                params['$$FIRST'] = first
                res = self._request(path, params, self.GET, fields)
                output += res
                first += limit
            return output

        return self._request(path, params, self.GET, fields)

    def count(self, objcode, params):
        """
        Count objects for a given set of filters (params).

        :param objcode: Object code to count.
        :param params:  Dict of criteria to use as filter
                        {'name': 'example task',
                         'name_Mod: 'cicontains'}
        :return:
        """

        path = '/{0}/count'.format(objcode)
        return self._request(path, params, self.GET)['count']

    def report(self, objcode, params, agg_field, agg_func, group_by_field=None, rollup=False):
        """
        Create aggregate reports.

        This method will return an aggregate for the fields specified in an object. For example:

        objcode = 'TASK', agg_func='duration'
        {
            "data": {
                "durationMinutes": 24468636,
                "dcount_ID": 3062
            }
        }

        :param objcode: Object type
        :param params:  Dict of criteria to use as filter
                        {'name': 'example task',
                         'name_Mod: 'cicontains'}

        :param agg_field: The field to aggregate on.
        :param agg_func: Type of function (sum, avg, etc)
        :param group_by_field: Group results by this field

                        "data": {
                            "Project 1": {
                                "durationMinutes": 24000,
                                "dcount_ID": 4,
                                "project_name": "Project 1"
                            },
                            "Project 2": {
                                "durationMinutes": 3360,
                                "dcount_ID": 1,
                                "project_name": "Project 1"
                            }
                        }

        :param rollup: Flag to indicate a roll-up of all groupings.

                        "data": {
                            "Project 1": {
                                "durationMinutes": 24000,
                                "dcount_ID": 4,
                                "project_name": "Project 1"
                            },
                            "Project 2": {
                                "durationMinutes": 3360,
                                "dcount_ID": 1,
                                "project_name": "Project 1"
                            },
                            "$$ROLLUP": {
                                "durationMinutes": 27600,
                                "dcount_ID": 5
                            }

        :return: dict with the results
        """

        path = "/{objCode}/report".format(objCode=objcode)

        if group_by_field:
            gb_key = "{field}_1_GroupBy".format(field=group_by_field)
            params[gb_key] = True

        if rollup:
            params['$$ROLLUP'] = True

        agg_key = '{field}_AggFunc'.format(field=agg_field)
        params[agg_key] = agg_func

        return self._request(path, params, self.GET)

    def make_update_as_user(self, user_email, exec_method, objcode, params, objid=None, action=None, objids=None,
                            fields=None, logout=False):
        """
        Performs an action on behalf of another user.

        This method will login on behalf of another user by passing in the users ID (email) and the API key to the login
        method. This will set a session ID. While the session ID is set all actions performed or taken will show as if
        done by the users.

        This is useful for script that might need to write updates on behalf of a user, change a commit date, or
        perform other operations that can only be done by a task assignee or owner.
        :param user_email: The email address of the users to act on behalf of
        :param exec_method: Method within Workfront class to execute on behalf of user
                            Options: ('post', 'put', 'action', 'search')
        :param action: Action to take ('post', 'put', 'action', 'search', 'report', 'bulk')
        :param objcode: The object code to act on
        :param params: A list of parameters
        :param objid: Optional. Object ID to act on. This is required for put, and certain action commands.
        :param objids: Optional. Object ID list to act on. This is required for bulk commands.
        :param fields: Optional. List of fields to return
        :return: The results of the query
        """
        res = self.login(user_email)

        commands = {'post': self.post,
                    'put': self.put,
                    'action': self.action,
                    'search': self.search,
                    'report': self.report,
                    'bulk': self.bulk}

        if res:
            if exec_method == 'post':
                return self.post(objcode, params, fields)

            elif exec_method == 'put':
                if objid:
                    return self.put(objcode, objid, params, fields)
                else:
                    raise ValueError('Must Pass object id if using put method')

            elif exec_method == 'action':
                if action:
                    return self.action(objcode, action, params, fields, objid)
                else:
                    raise ValueError('Must Pass action parameter if calling action method')

            elif exec_method == 'search':
                return self.search(objcode, params, fields)

            else:
                raise ValueError('Login failed. No Session ID')
        else:
            raise ValueError('Login Failed')

    def share_obj(self, obj_code, obj_id, user_ids, level='view'):
        # @todo finish and document this
        path = '/{0}/{1}/share'.format(obj_code, obj_id)

        access_levels = {'view': 'VIEW', 'contribute': 'CREATE', }
        params = []
        for user in user_ids:
            params.append({'accessorID': user,
                           'accessorObjCode': 'USER',
                           'coreAction': level})

        return self._request(path, params, self.PUT)['count']

    def get_obj_share(self, obj_code, obj_id):
        # @todo finish and document this section
        pass

    @staticmethod
    def _parse_parameter_lists(params):
        """
        Searches params and converts lists to comma sep strings

        The workfront API will reject the ['something','somethingelse'] format if sent as a parameter value. This
        method looks through the params for lists and converts them to simple comma separated values in a string. For
        example.

        {'status': ['CUR', 'PLN', 'APP'],
         'status_Mod': 'in'}

         will be converted to

        {'status': 'CUR',
         'status': 'PLN',
         'status': 'APP',
         'status_Mod': 'in'}

        :param params: A dict of the filter parameters
        :return: The filters params converted to a string
        """
        output_string = ""

        for key, value in params.items():
            if isinstance(value, list):
                # Convert list to multiple instances of same key.
                # Sort to make unit testing easier
                value = sorted(value)
                for list_item in value:
                    output_string = "{output_string}&{key}={value}".format(output_string=output_string,
                                                                           key=key, value=list_item)
            else:
                output_string = "{output_string}&{key}={value}".format(output_string=output_string, key=key,
                                                                       value=value)
        # There will be an & on the far left. Strip that off
        return output_string[1:]

    def _make_request(self, path, params, method, fields=None, raw=False):
        """
        Makes the request to Workfront API

        :param path: The API Path (i.e. http://domain.my.workfront.com/attask/api/v7.0/{action}/{obj})
        :param params: A dict of filter parameters
        :param method: The method (GET, POST, DELETE, PUT)
        :param fields: A list of fields to return
        :param raw: Flag to return data exactly as provided by API. The practical effect of this flag is to return
                    the value of the "data" key when set to False and the whole object when set to true. Example:

                    raw = True:
                    {'data': [{'ID':'ACB123...',
                               'name': 'proj 1'},
                               {'ID':'ACB156...',
                               'name': 'proj 2'}]
                    }

                    raw = False:
                    [{'ID':'ACB123...',
                     'name': 'proj 1'},
                     {'ID':'ACB156...',
                     'name': 'proj 2'}]

        :return: The query results
        """
        api_param_string = self._prepare_params(method, params, fields)

        api_path = self.api_base_url + path
        data = self._open_api_connection(api_param_string, api_path)

        return data if raw else data['data']

    def _p_open_api_connection(self, data, dest):
        """
        Makes the request to the Workfront API

        :param data: The URL parameters string
        :param dest: API URL
        :return: json results of query
        """
        if 'updates' in data:
            print('The length of the updates query is ' + str(len(data['updates'])) + 'char.')
        try:
            response = requests.get(dest, data)
        except requests.exceptions.HTTPError as e:
            msg = e.response
            raise WorkfrontAPIException(e)

        if response.ok:
            print('Response OK - 200. Len of full URL was ',len(response.url),' char.')
            return response.json()
        else:
            raise WorkfrontAPIException(response.text)


    def _prepare_params(self, method, params, fields):

        # If no params passed in set a blank dict.
        params = params if params else {}
        params['method'] = method
        params = self._set_authentication(params)

        if fields:
            params['fields'] = ','.join(fields)

        if method == self.GET and params:
            params = self._parse_parameter_lists(params)

        # @todo Check if we need to convert to ascii here. Might be able to just return data.
        return params

    def _set_authentication(self, params):
        """
        Adds the authentication into params.

        :param params:
        :return:
        """
        # Added a check to see if a session ID is being used instead of API Key - CL 8/4
        if self.session_id:
            params['sessionID'] = self.session_id
        elif self.api_key:
            params['apiKey'] = self.api_key
        else:
            raise ValueError("No valid authentication method provided. You must set either a sessionID or API Key.")

        return params

class get_obj_id(object):
    def _find_obj_id(self):
        pass



class wf_objects():
    pass

'''
{"noteText":comment,
                  "objID":issue_id,
                  "noteObjCode":"OPTASK"}
'''
class Project(WorkfrontObject):

    def __init__(self, api, project_id, data = None):
        if not data:
            data = {}
        self.params = {'ID': project_id}
        # params = params
        #super().__init__(data, api)
        #self.workfront_instance = workfront_instance
        self.project_id = project_id
        self.api = api
        #self.params = {'objID': self.project_id}
    def add_comment(self, comment_text):
        self.params['noteText'] = comment_text
        self.params['noteObjCode'] = 'PROJ'
        data = {'data': self.params}
        #wf_prj_comment = WorkfrontObject(self.params, self.workfront_instance)
        self.api.put('NOTE', self.project_id, self.params)


class Task():
    pass

class Issue():
    pass





class ObjCode:
    """
    Constants for Workfront objCode's
    """
    PROJECT = 'proj'
    TASK = 'task'
    ISSUE = 'optask'
    TEAM = 'team'
    HOUR = 'hour'
    TIMESHEET = 'tshet'
    USER = 'user'
    ASSIGNMENT = 'assgn'
    USER_PREF = 'userpf'
    CATEGORY = 'ctgy'
    CATEGORY_PARAMETER = 'ctgypa'
    PARAMETER = 'param'
    PARAMETER_GROUP = 'pgrp'
    PARAMETER_OPTION = 'popt'
    PARAMETER_VALUE = 'pval'
    ROLE = 'role'
    GROUP = 'group'
    NOTE = 'note'
    DOCUMENT = 'docu'
    DOCUMENT_VERSION = 'docv'
    EXPENSE = 'expns'
    CUSTOM_ENUM = 'custem'
    PROGRAM = 'prgm'
