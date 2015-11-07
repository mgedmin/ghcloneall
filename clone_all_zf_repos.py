#!/usr/bin/python3

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from operator import itemgetter


__author__ = 'Marius Gedminas <marius@gedmin.as>'
__licence__ = 'MIT'
__url__ = 'https://github.com/mgedmin/cloneall'
__version__ = '1.1.dev0'


# hardcoded configuration

ORGANIZATION = 'ZopeFoundation'


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

    Format of the JSON is documented at
    http://developer.github.com/v3/repos/#list-organization-repositories

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


class Progress(object):
    stream = sys.stdout
    last_message = ''
    format = '[{bar}] {cur}/{total}'
    bar_width = 20
    last_item = ''
    t_cursor_up = '\033[A'
    t_reset = '\033[m'
    t_green = '\033[32m'

    def status(self, message):
        if self.last_message:
            self.clear()
        self.stream.write('\r')
        self.stream.write(message)
        self.stream.write('\r')
        self.stream.flush()
        self.last_message = message

    def clear(self):
        self.stream.write('\r{}\r'.format(' ' * len(self.last_message.rstrip())))
        self.stream.flush()
        self.last_message = ''

    def message(self, cur, total):
        return self.format.format(cur=cur, total=total,
                                  bar=self.bar(cur, total))

    def scale(self, range, cur, total):
        return range * cur // max(total, 1)

    def bar(self, cur, total):
        n = self.scale(self.bar_width, cur, total)
        return ('=' * n).ljust(self.bar_width)

    def __call__(self, cur, total):
        self.status(self.message(cur, total))

    def item(self, msg):
        print(msg, file=self.stream)
        self.last_item = msg

    def update(self, msg, color=t_green):
        self.last_item += msg
        print(''.join([self.t_cursor_up, color, self.last_item, self.t_reset]),
              file=self.stream)


def main():
    parser = argparse.ArgumentParser(
        description="Clone/update all {} repositories from GitHub".format(ORGANIZATION))
    parser.add_argument('--version', action='version',
                        version="%(prog)s version " + __version__)
    parser.add_argument('--start-from', metavar='REPO',
                        help='skip all repositories that come before REPO alphabetically')
    args = parser.parse_args()
    progress = Progress()
    progress.status('Fetching list of {} repositories from GitHub...'.format(ORGANIZATION))
    list_url = 'https://api.github.com/orgs/{}/repos'.format(ORGANIZATION)
    repos = sorted(get_github_list(list_url), key=itemgetter('name'))
    progress.clear()
    for n, repo in enumerate(repos, 1):
        if args.start_from and repo['name'] < args.start_from:
            continue
        progress.item("+ {name}".format(**repo))
        progress(n, len(repos))
        dir = repo['name']
        if os.path.exists(dir):
            old_sha = subprocess.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
            subprocess.call(['git', 'pull', '-q', '--ff-only'], cwd=dir)
            new_sha = subprocess.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
            if old_sha != new_sha:
                progress.update(' (updated)')
        else:
            # use repo['ssh_url'] for writable checkouts
            subprocess.call(['git', 'clone', '-q', repo['git_url']])
            progress.update(' (new)')
        progress.clear()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
