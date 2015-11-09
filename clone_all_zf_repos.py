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
__version__ = '1.3.dev0'


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


def get_github_list(url, batch_size=100, progress_callback=None):
    """Perform (a series of) HTTP GETs for a URL, return deserialized JSON.

    Format of the JSON is documented at
    http://developer.github.com/v3/repos/#list-organization-repositories

    Supports batching (which GitHub indicates by the presence of a Link header,
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
        if progress_callback:
            progress_callback(len(res))
        more, headers = get_json_and_headers('{}?page={}&per_page={}'.format(
                                                    url, page, batch_size))
        res += more
    return res


class Progress(object):
    """A progress bar.

    There are two parts of progress output:

    - a scrolling list of items
    - a progress bar (or status message) at the bottom

    These are controlled by the following API methods:

    - status(msg) replaces the progress bar with a status message
    - clear() clears the progress bar/status message
    - set_total(n) defines how many items there will be in total
    - item(text) shows an item and updates the progress bar
    - update(extra_text) updates the last item (and highlights it in a
      different color)

    """
    stream = sys.stdout
    last_message = ''
    format = '[{bar}] {cur}/{total}'
    bar_width = 20
    last_item = ''
    t_cursor_up = '\033[A'
    t_reset = '\033[m'
    t_green = '\033[32m'
    cur = total = 0

    def status(self, message):
        """Replace the status message."""
        self.clear()
        if message:
            self.stream.write('\r')
            self.stream.write(message)
            self.stream.write('\r')
            self.stream.flush()
            self.last_message = message

    def clear(self):
        """Clear the status message."""
        if self.last_message:
            self.stream.write('\r{}\r'.format(' ' * len(self.last_message.rstrip())))
            self.stream.flush()
            self.last_message = ''

    def progress(self):
        self.status(self.message(self.cur, self.total))

    def message(self, cur, total):
        return self.format.format(cur=cur, total=total,
                                  bar=self.bar(cur, total))

    def scale(self, range, cur, total):
        return range * cur // max(total, 1)

    def bar(self, cur, total):
        n = self.scale(self.bar_width, cur, total)
        return ('=' * n).ljust(self.bar_width)

    def set_limit(self, total):
        """Specify the expected total number of items.

        E.g. if you set_limit(10), this means you expect to call item() ten
        times.
        """
        self.total = total
        self.progress()

    def item(self, msg):
        """Show an item and update the progress bar."""
        self.clear()
        print(msg, file=self.stream)
        self.last_item = msg
        self.extra_info_lines = 0
        self.cur += 1
        self.progress()

    def update(self, msg, color=t_green):
        """Update the last shown item and highlight it."""
        self.last_item += msg
        print(''.join([self.t_cursor_up * (1 + self.extra_info_lines),
                       color, self.last_item, self.t_reset,
                       '\n' * self.extra_info_lines]),
              file=self.stream)

    def extra_info(self, msg):
        """Print some extra information."""
        self.clear()
        for line in msg.splitlines():
            print('   ', line, file=self.stream)
            self.extra_info_lines += 1


class RepoWrangler(object):

    def __init__(self, dry_run=False, verbose=0, progress=None):
        self.n_repos = 0
        self.n_updated = 0
        self.n_new = 0
        self.n_dirty = 0
        self.dry_run = dry_run
        self.verbose = verbose or 0
        self.progress = progress if progress else Progress()

    def repo_dir(self, repo):
        return repo['name']

    def repo_url(self, repo):
        # use repo['git_url'] for anonymous checkouts, but they'e slower
        # (at least as long as you use SSH connection multiplexing)
        return repo['ssh_url']

    def decode(self, output):
        return output.decode('UTF-8', 'replace')

    def branch_name(self, head):
        if head.startswith('refs/'):
            head = head[len('refs/'):]
        if head.startswith('heads/'):
            head = head[len('heads/'):]
        return head

    def call(self, args, **kwargs):
        retcode = subprocess.call(args, **kwargs)
        return retcode

    def check_output(self, args, **kwargs):
        output = subprocess.check_output(args, **kwargs)
        return self.decode(output)

    def process(self, repo):
        self.progress.item("+ {name}".format(**repo))
        dir = self.repo_dir(repo)
        if os.path.exists(dir):
            self.update(repo, dir)
            self.verify(repo, dir)
        else:
            self.clone(repo, dir)
        self.n_repos += 1

    def clone(self, repo, dir):
        if not self.dry_run:
            url = self.repo_url(repo)
            self.call(['git', 'clone', '-q', url])
        self.progress.update(' (new)')
        self.n_new += 1

    def update(self, repo, dir):
        if not self.dry_run:
            old_sha = self.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
            self.call(['git', 'pull', '-q', '--ff-only'], cwd=dir)
            new_sha = self.check_output(['git', 'describe', '--always', '--dirty'], cwd=dir)
            if old_sha != new_sha:
                self.progress.update(' (updated)')
                self.n_updated += 1

    def verify(self, repo, dir):
        dirty = 0
        if self.has_local_changes(dir):
            self.progress.update(' (local changes)')
            dirty = 1
        if self.has_staged_changes(dir):
            self.progress.update(' (staged changes)')
            dirty = 1
        if self.has_local_commits(dir):
            self.progress.update(' (local commits)')
            dirty = 1
        branch = self.get_current_branch(dir)
        if branch != 'master':
            self.progress.update(' (not on master)')
            if self.verbose >= 2:
                self.progress.extra_info('branch: {}'.format(branch))
            dirty = 1
        if self.verbose:
            remote_url = self.get_remote_url(dir)
            if remote_url != repo['ssh_url'] and remote_url + '.git' != repo['ssh_url']:
                self.progress.update(' (wrong remote url)')
                if self.verbose >= 2:
                    self.progress.extra_info('remote: {}'.format(remote_url))
                dirty = 1
        if self.verbose:
            unknown_files = self.get_unknown_files(dir)
            if unknown_files:
                self.progress.update(' (unknown files)')
                if self.verbose >= 2:
                    for n, fn in enumerate(unknown_files):
                        if self.verbose < 3 and n == 10:
                            self.progress.extra_info('(and %d more)' % (len(files) - n))
                            break
                        self.progress.extra_info(fn)
                dirty = 1
        self.n_dirty += dirty

    def has_local_changes(self, dir):
        # command borrowed from /usr/lib/git-core/git-sh-prompt
        return self.call(['git', 'diff', '--no-ext-diff', '--quiet', '--exit-code'], cwd=dir) != 0

    def has_staged_changes(self, dir):
        # command borrowed from /usr/lib/git-core/git-sh-prompt
        return self.call(['git', 'diff-index', '--cached', '--quiet', 'HEAD', '--'], cwd=dir) != 0

    def has_local_commits(self, dir):
        return self.check_output(['git', 'rev-list', '@{u}..'], cwd=dir) != ''

    def get_current_head(self, dir):
        return self.check_output(['git', 'symbolic-ref', 'HEAD'], cwd=dir).strip()

    def get_current_branch(self, dir):
        return self.branch_name(self.get_current_head(dir))

    def get_remote_url(self, dir):
        return self.check_output(['git', 'ls-remote', '--get-url'], cwd=dir).strip()

    def get_unknown_files(self, dir):
        # command borrowed from /usr/lib/git-core/git-sh-prompt
        return self.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', ':/*'], cwd=dir).splitlines()


def main():
    parser = argparse.ArgumentParser(
        description="Clone/update all organization repositories from GitHub")
    parser.add_argument('--version', action='version',
                        version="%(prog)s version " + __version__)
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help="don't pull/clone, just print what would be done")
    parser.add_argument('-v', '--verbose', action='count',
                        help="perform additional checks")
    parser.add_argument('--start-from', metavar='REPO',
                        help='skip all repositories that come before REPO alphabetically')
    parser.add_argument('--organization', default=DEFAULT_ORGANIZATION,
                        help='specify the GitHub organization (default: %s)' % DEFAULT_ORGANIZATION)
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
    def progress_callback(n):
        progress.status('Fetching list of {} repositories from GitHub... ({})'.format(args.organization, n))
    list_url = 'https://api.github.com/orgs/{}/repos'.format(args.organization)
    repos = sorted(get_github_list(list_url, progress_callback=progress_callback), key=itemgetter('name'))
    progress.clear()
    progress.set_limit(len(repos))
    wrangler = RepoWrangler(dry_run=args.dry_run, verbose=args.verbose, progress=progress)
    for n, repo in enumerate(repos, 1):
        if args.start_from and repo['name'] < args.start_from:
            continue
        wrangler.process(repo)
    progress.clear()
    print("{0.n_repos} repositories: {0.n_updated} updated, {0.n_new} new, {0.n_dirty} dirty.".format(wrangler))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
