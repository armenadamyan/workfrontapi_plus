from datetime import datetime


class Tools(object):
    @staticmethod
    def parse_workfront_date(date_string):
        """
        Converts from the Workfront datetime format into a Python datetime object

        :param date_string: The workfront date string. Example "2017-01-01T01:01:00.000-0800"
        :return: A datetime object
        """
        return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S:%f%z")

    @staticmethod
    def flatten_response(data, skip_keys=None, use_keys=None, pretty=False):
        """
        Flattens out nested dict

        This method will take a Workfront API response and "flatten out" certain nested dicts.
        For example, here is a response for a task
        [{'ID': 'abc123...',
          'name': 'test task',
          'project': {'ID': 'cde456',
                      'name': 'My Proj'}
          }]

        would be converted to
        [{'ID': 'abc123...',
          'name': 'test task',
          'project:ID': 'cde456',
          'project:name': 'My Proj'
          }]

        :param data:
        :param skip_keys:
        :param use_keys:
        :param pretty: Removes the project:name style notation. Example:
                with pretty set to true
                [{'ID': 'abc123...',
                  'Name': 'test task',
                  'Project ID': 'cde456',
                  'Project Name': 'My Proj'
                  }]
        :return: A processed list or dict
        """
        # @todo build flatten response method
        pass

    @staticmethod
    def text_mode(text):
        """
        Converts Workfront "Text Mode" into a parameter string.

        :param text: A string containing Workfront text mode parameters
        :return: A dict version of the passed in parameters
        """
        output = {}

        for line in text.splitlines():

            key, value = line.split("=")

            # key = key_pair[0].strip()
            # value = key_pair[1].strip()

            if "\t" in value:
                # It's a list
                value_list = value.split("\t")
                output[key] = value_list
            else:
                output[key] = value
        return output
