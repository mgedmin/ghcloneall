#!/usr/bin/python3

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from operator import itemgetter

import requests
import requests_cache


__author__ = 'Marius Gedminas <marius@gedmin.as>'
__licence__ = 'MIT'
__url__ = 'https://github.com/mgedmin/cloneall'
__version__ = '1.2.dev0'


DEFAULT_ORGANIZATION = 'ZopeFoundation'


class Error(Exception):
    """An error that is not a bug in this script."""


def get_json_and_headers(url):
    """Perform HTTP GET for a URL, return deserialized JSON and headers.

    Returns a tuple (json_data, headers) where headers is something dict-like.
    """
    r = requests.get(url)
    if 400 <= r.status_code < 500:
        raise Error("Failed to fetch {}:\n{}".format(url, r.json()['message']))
    return r.json(), r.headers


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
        description="Clone/update all organization repositories from GitHub")
    parser.add_argument('--version', action='version',
                        version="%(prog)s version " + __version__)
    parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run',
                        help="don't pull/clone, just print what would be done")
    parser.add_argument('--start-from', metavar='REPO',
                        help='skip all repositories that come before REPO alphabetically')
    parser.add_argument('--organization', default=DEFAULT_ORGANIZATION,
                        help='specify the GitHub organization')
    parser.add_argument('--http-cache', default='.httpcache', metavar='DBNAME',
                        # .sqlite will be appended automatically
                        help='cache HTTP requests on disk in an sqlite database (default: .httpcache)')
    parser.add_argument('--no-http-cache', action='store_false', dest='http_cache',
                        help='disable HTTP disk caching')
    args = parser.parse_args()
    if args.http_cache:
        requests_cache.install_cache(args.http_cache,
                                     backend='sqlite',
                                     expire_after=300)

    progress = Progress()
    progress.status('Fetching list of {} repositories from GitHub...'.format(args.organization))
    list_url = 'https://api.github.com/orgs/{}/repos'.format(args.organization)
    repos = sorted(get_github_list(list_url), key=itemgetter('name'))
    progress.clear()
    n_fetched = n_updated = n_new = n_dirty = 0
    for n, repo in enumerate(repos, 1):
        if args.start_from and repo['name'] < args.start_from:
            continue
        progress.item("+ {name}".format(**repo))
        progress(n, len(repos))
        n_fetched += 1
        dir = repo['name']
        if os.path.exists(dir):
            if not args.dry_run:
                old_sha = subprocess.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
                subprocess.call(['git', 'pull', '-q', '--ff-only'], cwd=dir)
                new_sha = subprocess.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
                if old_sha != new_sha:
                    progress.update(' (updated)')
                    n_updated += 1
            # commands borrowed from /usr/lib/git-core/git-sh-prompt
            dirty = 0
            if subprocess.call(['git', 'diff', '--no-ext-diff', '--quiet', '--exit-code'], cwd=dir) != 0:
                progress.update(' (local changes)')
                dirty = 1
            if subprocess.call(['git', 'diff-index', '--cached', '--quiet', 'HEAD', '--'], cwd=dir) != 0:
                progress.update(' (staged changes)')
                dirty = 1
            if subprocess.check_output(['git', 'rev-list', '@{u}..'], cwd=dir) != b'':
                progress.update(' (local commits)')
                dirty = 1
            if subprocess.check_output(['git', 'symbolic-ref', 'HEAD'], cwd=dir) != b'refs/heads/master\n':
                progress.update(' (not on master)')
                dirty = 1
            n_dirty += dirty
        else:
            if not args.dry_run:
                # use repo['git_url'] for anonymous checkouts
                subprocess.call(['git', 'clone', '-q', repo['ssh_url']])
            progress.update(' (new)')
            n_new += 1
        progress.clear()
    print("{n_fetched} repositories: {n_updated} updated, {n_new} new, {n_dirty} dirty.".format(
          n_fetched=n_fetched, n_updated=n_updated, n_new=n_new, n_dirty=n_dirty))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
