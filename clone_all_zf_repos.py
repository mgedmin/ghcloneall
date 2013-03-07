#!/usr/bin/python3

import json
import os
import subprocess
import urllib.request


class Error(Exception):
    """An error that is not a bug in this script."""


def get_json_and_headers(url):
    """Perform HTTP GET for a URL, return deserialized JSON and headers.

    Returns a tuple (json_data, headers) where headers is an instance
    of email.message.Message (because that's what urllib gives us).
    """
    with urllib.request.urlopen(url) as r:
        # We expect Github to return UTF-8, but let's verify that.
        content_type = r.info().get('Content-Type', '').lower()
        if content_type not in ('application/json; charset="utf-8"',
                                'application/json; charset=utf-8'):
            raise Error('Did not get UTF-8 JSON data from {}, got {}'
                        .format(url, content_type))
        return json.loads(r.read().decode('UTF-8')), r.info()


def get_github_list(url, batch_size=100):
    """Perform (a series of) HTTP GETs for a URL, return deserialized JSON.

    Supports batching (which Github indicates by the presence of a Link header,
    e.g. ::

        Link: <https://api.github.com/resource?page=2>; rel="next",
              <https://api.github.com/resource?page=5>; rel="last"

    """
    # API documented at http://developer.github.com/v3/#pagination
    res, headers = get_json_and_headers('{}?per_page={}'.format(
                                                url, batch_size))
    page = 1
    while 'rel="next"' in headers.get('Link', ''):
        page += 1
        more, headers = get_json_and_headers('{}?page={}&per_page={}'.format(
                                                    url, page, batch_size))
        res += more
    return res


ZOPE_GITHUB_LIST = 'https://api.github.com/orgs/ZopeFoundation/repos'
EXCEPTIONS = set()


def main():
    for repo in get_github_list(ZOPE_GITHUB_LIST):
        print("+ {full_name}".format(**repo))
        dir = repo['name']
        if os.path.exists(dir):
            subprocess.call(['git', 'pull', '-q', '--ff-only'], cwd=dir)
        else:
            subprocess.call(['git', 'clone', '-q', repo['git_url']])


if __name__ == '__main__':
    main()
