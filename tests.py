import os
import re
import subprocess
import sys
from io import StringIO

import pytest
import requests
import requests_cache

import ghcloneall


class MockResponse:

    def __init__(self, status_code=200, json=None, links={}):
        assert json is not None
        self.status_code = status_code
        self.links = {
            rel: dict(rel=rel, url=url)
            for rel, url in links.items()
        }
        self._json = json

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError()


class MockRequestGet:

    user_endpoint = 'https://api.github.com/user'

    def __init__(self):
        self.responses = {}
        self.not_found = MockResponse(
            status_code=404, json={'message': 'not found'},
        )

    def update(self, responses):
        self.responses.update(responses)

    def set_user(self, user):
        if user is None:
            if self.user_endpoint in self.responses:
                del self.responses[self.user_endpoint]
        else:
            self.responses[self.user_endpoint] = MockResponse(
                json={'login': user},
            )

    def __call__(self, url, headers=None):
        return self.responses.get(url, self.not_found)


@pytest.fixture(autouse=True)
def mock_requests_get(monkeypatch):
    mock_get = MockRequestGet()
    monkeypatch.setattr(requests, 'get', mock_get)
    monkeypatch.setattr(requests.Session, 'get', mock_get)
    mock_get.set_user(None)
    return mock_get


@pytest.fixture(autouse=True)
def mock_requests_cache(monkeypatch):
    monkeypatch.setattr(requests_cache, 'install_cache', lambda *a, **kw: None)


class MockPopen:
    def __init__(self, stdout=b'', stderr=b'', rc=0):
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc

    def __call__(self, args, stdout=None, stderr=None, cwd=None):
        new_stdout = self.stdout
        new_stderr = self.stderr
        if stderr == subprocess.STDOUT:
            new_stdout += new_stderr
            new_stderr = None
        elif stderr != subprocess.PIPE:
            new_stderr = None
        if stdout != subprocess.PIPE:
            new_stdout = None
        return MockPopen(new_stdout, new_stderr, self.rc)

    def communicate(self):
        return self.stdout, self.stderr

    def wait(self):
        return self.rc


@pytest.fixture(autouse=True)
def mock_subprocess_Popen(monkeypatch):
    mock_Popen = MockPopen()
    monkeypatch.setattr(subprocess, 'Popen', mock_Popen)
    return mock_Popen


@pytest.fixture(autouse=True)
def mock_config_filename(monkeypatch):
    monkeypatch.setattr(ghcloneall, 'CONFIG_FILE', '/dev/null')


def make_page_url(url, page, extra):
    # Some of the incoming test URLs already have query args. If so,
    # append the page arguments using the appropriate separator.
    sep = '?'
    if '?' in url:
        sep = '&'
    if page == 1:
        return '%s%s%sper_page=100' % (url, sep, extra)
    else:
        return '%s%s%spage=%d&per_page=100' % (url, sep, extra, page)


def mock_multi_page_api_responses(url, pages, extra='sort=full_name&'):
    assert len(pages) > 0
    responses = {}
    for n, page in enumerate(pages, 1):
        page_url = make_page_url(url, n, extra)
        links = {}
        if n != len(pages):
            next_page_url = make_page_url(url, n + 1, extra)
            links['next'] = next_page_url
        responses[page_url] = MockResponse(json=page, links=links)
    return responses


class Terminal:

    def __init__(self, width=80, height=24):
        self.rows = [[' ']*width for n in range(height)]
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height

    def __str__(self):
        return '\n'.join(''.join(row).rstrip() for row in self.rows).rstrip()

    def output(self, text):
        for s in re.split(r'(\033\[\d*[a-zA-Z]|.)', text):
            if s == '\r':
                self.x = 0
            elif s == '\n':
                self.newline()
            elif len(s) == 1:
                self.put_char(s)
            elif s.startswith('\033['):
                command = s[-1:]
                param = s[2:-1]
                if param:
                    param = int(param)
                else:
                    param = 0
                self.control_seq(command, param)

    def put_char(self, c):
        self.rows[self.y][self.x] = c
        self.x += 1
        if self.x == self.width:
            self.newline()

    def newline(self):
        self.x = 0
        self.y += 1
        if self.y == self.height:
            self.y -= 1
            self.delete_line(0)

    def insert_line(self, y):
        self.rows.insert(y, [' '] * self.width)
        del self.rows[-1]

    def delete_line(self, y):
        del self.rows[y]
        self.rows.append([' '] * self.width)

    def control_seq(self, command, param):
        if command == 'A':
            # move cursor up
            self.y -= param
            if self.y < 0:
                # not 100% sure what real terminals do here
                self.y = 0
        elif command == 'B':
            # move cursor down
            self.y += param
            if self.y >= self.height - 1:
                # not 100% sure what real terminals do here
                self.y = self.height - 1
        elif command == 'L':
            for n in range(param):
                self.insert_line(self.y)
        elif command == 'M':
            for n in range(param):
                self.delete_line(self.y)


def show_ansi(text):
    """Make ANSI control sequences visible."""
    replacements = {
        '\033[1A': '{up1}',
        '\033[2A': '{up2}',
        '\033[1B': '{down1}',
        '\033[1L': '{ins1}',
        '\033[2L': '{ins2}',
        '\033[1M': '{del1}',
        '\033[31m': '{red}',
        '\033[32m': '{green}',
        '\033[33m': '{brown}',
        '\033[m': '{reset}',
        '\033': '{esc}',
        '\r': '{cr}',
    }
    pattern = '|'.join(
        re.escape(s) for s in sorted(replacements, key=len, reverse=True)
    )
    return re.sub(pattern, lambda m: replacements[m.group(0)], text)


def show_ansi_result(text, width=80, height=24):
    term = Terminal(width, height)
    term.output(text)
    return str(term)


def compare(actual, expected):
    assert show_ansi(actual) == show_ansi(expected)


def test_get_json_and_links(mock_requests_get):
    url = 'https://github.example.com/api'
    mock_requests_get.update({
        url: MockResponse(
            json={'json': 'data'},
            links={'next': 'https://github.example.com/api?page=2'},
        ),
    })
    data, links = ghcloneall.get_json_and_links(url)
    assert data == {'json': 'data'}
    assert links == {
        'next': {
            'rel': 'next',
            'url': 'https://github.example.com/api?page=2',
        },
    }


def test_get_json_and_links_failure(mock_requests_get):
    url = 'https://github.example.com/api'
    mock_requests_get.update({
        url: MockResponse(
            status_code=400,
            json={'message': 'this request is baaad'},
        ),
    })
    with pytest.raises(ghcloneall.Error):
        ghcloneall.get_json_and_links(url)


def test_get_github_list(mock_requests_get):
    mock_requests_get.update({
        'https://github.example.com/api?per_page=100': MockResponse(
            json=[{'item': 1}, {'item': 2}],
            links={
                'next': 'https://github.example.com/api?page=2&per_page=100',
            }),
        'https://github.example.com/api?page=2&per_page=100': MockResponse(
            json=[{'item': 3}, {'item': 4}],
            links={
                'next': 'https://github.example.com/api?page=3&per_page=100',
            }),
        'https://github.example.com/api?page=3&per_page=100': MockResponse(
            json=[{'item': 5}]),
    })
    url = 'https://github.example.com/api'
    progress = []
    res = ghcloneall.get_github_list(url, progress_callback=progress.append)
    assert res == [
        {'item': 1},
        {'item': 2},
        {'item': 3},
        {'item': 4},
        {'item': 5},
    ]
    assert progress == [2, 4]


def test_Progress(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    progress.status("hello")
    progress.status("world")
    progress.finish("bye")
    assert buf.getvalue() == (
        '\rhello\r'
        '\r     \r'
        '\rworld\r'
        '\r     \r'
        'bye\n'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'bye'
    )


def test_Progress_no_output_after_finish(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    progress.status("hi")
    progress.finish()
    # these are all ignored
    progress.status("ho")
    progress.clear()
    item = progress.item("boo")
    item.hide()
    item.extra_info("hooo")
    assert buf.getvalue() == (
        '\rhi\r'
        '\r  \r'
    )
    assert show_ansi_result(buf.getvalue()) == ''


def test_Progress_progress(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    progress.progress()
    assert buf.getvalue() == (
        '\r[....................] 0/0\r'
    )
    progress.set_limit(5)
    assert buf.getvalue() == (
        '\r[....................] 0/0\r'
        '\r                          \r'
        '\r[....................] 0/5\r'
    )
    progress.item()
    assert buf.getvalue() == (
        '\r[....................] 0/0\r'
        '\r                          \r'
        '\r[....................] 0/5\r'
        '\r                          \r'
        '\r[####................] 1/5\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        '[####................] 1/5'
    )


def test_Progress_context_manager(capsys):
    buf = StringIO()
    with pytest.raises(KeyboardInterrupt):
        with ghcloneall.Progress(stream=buf) as progress:
            progress.item()
            raise KeyboardInterrupt()
    assert buf.getvalue() == (
        '\r[####################] 1/0\r'
        '\r                          \r'
        'Interrupted\n'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'Interrupted'
    )


def test_Progress_item_details(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.update(" - all good")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r{up1}{green}first repo - all good{reset}\r{down1}'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo - all good\n'
        '[####################] 1/0'
    )


def test_Progress_item_failure(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.update(" - all bad", failed=True)
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r{up1}{red}first repo - all bad{reset}\r{down1}'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo - all bad\n'
        '[####################] 1/0'
    )


def test_Progress_item_finished(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.finished()
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r{up1}first repo\r{down1}'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '[####################] 1/0'
    )


def test_Progress_item_finished_and_hidden(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.finished(hide=True)
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '{up1}{del1}'
    )
    assert show_ansi_result(buf.getvalue()) == (
        '[####################] 1/0'
    )


def test_Progress_item_once_hidden_stays_hidden(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.finished(hide=True)
    item.update("ha ha")
    item.hide()
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '{up1}{del1}'
    )
    assert show_ansi_result(buf.getvalue()) == (
        '[####################] 1/0'
    )


def test_Progress_extra_info(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.extra_info("this is a very good repo btw")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '{ins1}    this is a very good repo btw\n'
        # plus a redraw in case the insertion pushed the progress bar offscreen
        '\r                          \r'
        '\r[####################] 1/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '    this is a very good repo btw\n'
        '[####################] 1/0'
    )


def test_Progress_error_info(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.error_info("oopsies")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        # new output
        '{ins1}    {red}oopsies{reset}\n'
        # plus a redraw in case the insertion pushed the progress bar offscreen
        '\r                          \r'
        '\r[####################] 1/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '    oopsies\n'
        '[####################] 1/0'
    )


def test_Progress_extra_info_but_not_really(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.extra_info("")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '[####################] 1/0'
    )


def test_Progress_extra_info_multiple_lines(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item = progress.item("first repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
    )
    item.extra_info("hi\nho")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        # new output
        '{ins2}    hi\n'
        '    ho\n'
        '\r                          \r'
        '\r[####################] 1/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '    hi\n'
        '    ho\n'
        '[####################] 1/0'
    )


def test_Progress_extra_info_not_last_item(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item1 = progress.item("first repo")
    progress.item("second repo")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r                          \r'
        '{brown}second repo{reset}\n'
        '\r[####################] 2/0\r'
    )
    item1.extra_info("wow such magic")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r                          \r'
        '{brown}second repo{reset}\n'
        '\r[####################] 2/0\r'
        # new output
        '{up1}{ins1}    wow such magic\n'
        # plus a redraw of everything below the updated item in case the
        # insertion pushed the progress bar offscreen
        '{brown}second repo{reset}\n'
        '\r                          \r'
        '\r[####################] 2/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '    wow such magic\n'
        'second repo\n'
        '[####################] 2/0'
    )


def test_Progress_extra_info_not_last_item_redraws_all_below(capsys):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    item1 = progress.item("first repo")
    item2 = progress.item("second repo")
    item2.extra_info("k")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r                          \r'
        '{brown}second repo{reset}\n'
        '\r[####################] 2/0\r'
        '{ins1}    k\n'
        '\r                          \r'
        '\r[####################] 2/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        'second repo\n'
        '    k\n'
        '[####################] 2/0'
    )
    item1.extra_info("wow such magic")
    compare(
        buf.getvalue(),
        '{brown}first repo{reset}\n'
        '\r[####################] 1/0\r'
        '\r                          \r'
        '{brown}second repo{reset}\n'
        '\r[####################] 2/0\r'
        '{ins1}    k\n'
        '\r                          \r'
        '\r[####################] 2/0\r'
        # new output
        '{up2}{ins1}    wow such magic\n'
        # plus a redraw of everything below the updated item in case the
        # insertion pushed the progress bar offscreen
        '{brown}second repo{reset}\n'
        '    k\n'
        '\r                          \r'
        '\r[####################] 2/0\r'
    )
    assert show_ansi_result(buf.getvalue()) == (
        'first repo\n'
        '    wow such magic\n'
        'second repo\n'
        '    k\n'
        '[####################] 2/0'
    )


def test_Repo():
    r1 = ghcloneall.Repo('foo', 'git@github.com:test_user/foo.git',
                         ['https://github.com/test_user/foo'])
    r2 = ghcloneall.Repo('foo', 'git@github.com:test_user/foo.git',
                         ['https://github.com/test_user/foo'])
    r3 = ghcloneall.Repo('bar', 'git@github.com:test_user/bar.git',
                         ['https://github.com/test_user/bar'])
    assert r1 == r2
    assert not r1 != r2
    assert r1 != r3
    assert not r1 == r3
    assert r1 != 'foo'
    assert not r1 == 'foo'
    assert repr(r1) == (
        "Repo('foo', 'git@github.com:test_user/foo.git',"
        " {'git@github.com:test_user/foo.git',"
        " 'https://github.com/test_user/foo'})"
    )


def gist(name, **kwargs):
    repo = {
        'id': name,
        'public': True,
        'git_pull_url': 'https://gist.github.com/%s.git' % name,
        'git_push_url': 'https://gist.github.com/%s.git' % name,
    }
    repo.update(kwargs)
    return repo


def Gist(name, **kwargs):
    return ghcloneall.Repo.from_gist(gist(name, **kwargs))


def test_RepoWrangler_auth():
    token = 'UNITTEST'
    wrangler = ghcloneall.RepoWrangler(token=token)
    assert wrangler.session.auth == ('', token)


def test_RepoWrangler_list_gists(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/gists',
        extra='',
        pages=[
            [
                gist('9999'),
                gist('1234'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_gists(user='test_user')
    assert result == [
        Gist('1234'),
        Gist('9999'),
    ]


def test_RepoWrangler_list_gists_filtering(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/gists',
        extra='',
        pages=[
            [
                gist('9999'),
                gist('1234'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_gists(user='test_user', pattern='9*')
    assert result == [
        Gist('9999'),
    ]


def repo(name, **kwargs):
    repo = {
        'name': name,
        'archived': False,
        'fork': False,
        'private': False,
        'disabled': False,
        'clone_url': 'https://github.com/test_user/%s' % name,
        'ssh_url': 'git@github.com:test_user/%s.git' % name,
        'default_branch': 'master',
    }
    repo.update(kwargs)
    return repo


def Repo(name, **kwargs):
    return ghcloneall.Repo.from_repo(repo(name, **kwargs))


def test_RepoWrangler_list_repos_for_user(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/repos',
        pages=[
            [
                repo('xyzzy'),
                repo('project-foo'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_repos(user='test_user')
    assert result == [
        Repo('project-foo'),
        Repo('xyzzy'),
    ]


def test_RepoWrangler_list_repos_for_org(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/orgs/test_org/repos',
        pages=[
            [
                repo('xyzzy'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_repos(organization='test_org')
    assert result == [
        Repo('xyzzy'),
    ]


def test_RepoWrangler_list_repos_filter_by_name(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/repos',
        pages=[
            [
                repo('xyzzy'),
                repo('project-foo'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_repos(user='test_user', pattern='pr*')
    assert result == [
        Repo('project-foo'),
    ]


def test_RepoWrangler_list_repos_filter_by_status(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/repos',
        pages=[
            [
                repo('a', archived=True),
                repo('f', fork=True),
                repo('p', private=True),
                repo('d', private=True, disabled=True),
                repo('c'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_repos(user='test_user')
    assert result == [
        Repo('c'),
        Repo('d', private=True, disabled=True),
        Repo('p', private=True),
    ]
    result = wrangler.list_repos(user='test_user', include_archived=True)
    assert result == [
        Repo('a', archived=True),
        Repo('c'),
        Repo('d', private=True, disabled=True),
        Repo('p', private=True),
    ]
    result = wrangler.list_repos(user='test_user', include_forks=True)
    assert result == [
        Repo('c'),
        Repo('d', private=True, disabled=True),
        Repo('f', fork=True),
        Repo('p', private=True),
    ]
    result = wrangler.list_repos(user='test_user', include_disabled=False)
    assert result == [
        Repo('c'),
        Repo('p', private=True),
    ]


def test_RepoWrangler_list_repos_no_private(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/repos',
        pages=[
            [
                repo('a', archived=True),
                repo('f', fork=True),
                repo('p', private=True),
                repo('d', disabled=True),
                repo('c'),
            ],
        ],
    ))
    wrangler = ghcloneall.RepoWrangler()
    result = wrangler.list_repos(user='test_user', include_private=False)
    assert result == [
        Repo('c'),
        Repo('d', disabled=True),
    ]
    result = wrangler.list_repos(user='test_user', include_private=False,
                                 include_archived=True)
    assert result == [
        Repo('a', archived=True),
        Repo('c'),
        Repo('d', disabled=True),
    ]
    result = wrangler.list_repos(user='test_user', include_private=False,
                                 include_forks=True)
    assert result == [
        Repo('c'),
        Repo('d', disabled=True),
        Repo('f', fork=True),
    ]
    result = wrangler.list_repos(user='test_user', include_private=False,
                                 include_disabled=False)
    assert result == [
        Repo('c'),
    ]
    result = wrangler.list_repos(user='test_user', include_private=False)
    assert result == [
        Repo('c'),
        Repo('d', disabled=True),
    ]


def test_RepoWrangler_list_repos_progress_bar(mock_requests_get):
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/test_user/repos',
        pages=[
            [
                repo('xyzzy'),
            ],
            [
                repo('project-foo'),
            ],
        ],
    ))
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    result = wrangler.list_repos(user='test_user')
    assert result == [
        Repo('project-foo'),
        Repo('xyzzy'),
    ]
    compare(
        buf.getvalue(),
        "{cr}Fetching list of test_user's repositories from GitHub...{cr}"
        "{cr}                                                        {cr}"
        "{cr}Fetching list of test_user's repositories from GitHub... (1){cr}"
    )


def test_RepoWrangler_list_repos_missing_arguments():
    wrangler = ghcloneall.RepoWrangler()
    with pytest.raises(ValueError):
        wrangler.list_repos()


def test_RepoWrangler_repo_task(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', lambda dir: False)
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    compare(
        buf.getvalue(),
        "{brown}+ xyzzy{reset}\n"
        "{cr}[####################] 1/0{cr}"
    )
    task.run()
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (new)\n'
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 1
    assert wrangler.n_updated == 0
    assert wrangler.n_dirty == 0


def test_RepoTask_run_updates(monkeypatch, ):
    monkeypatch.setattr(os.path, 'exists', lambda dir: True)
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    responses = ['aaaaa', 'bbbbb']
    task.get_current_commit = lambda dir: responses.pop(0)
    task.get_current_branch = lambda dir: 'master'
    task.run()
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (updated)\n'
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 0
    assert wrangler.n_updated == 1
    assert wrangler.n_dirty == 0


def test_RepoTask_run_updates_main(monkeypatch, ):
    monkeypatch.setattr(os.path, 'exists', lambda dir: True)
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy', default_branch='main'))
    responses = ['aaaaa', 'bbbbb']
    task.get_current_commit = lambda dir: responses.pop(0)
    task.get_current_branch = lambda dir: 'main'
    task.run()
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (updated)\n'
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 0
    assert wrangler.n_updated == 1
    assert wrangler.n_dirty == 0


def raise_exception(*args):
    raise Exception("oh no")


def test_RepoTask_run_handles_errors(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', lambda dir: False)
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    task.clone = raise_exception
    task.run()
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    Exception: oh no\n'
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 0
    assert wrangler.n_updated == 0
    assert wrangler.n_dirty == 0


def test_RepoTask_run_in_quiet_mode(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', lambda dir: True)
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, quiet=True)
    task = wrangler.repo_task(Repo('xyzzy'))
    task.get_current_branch = lambda dir: 'master'
    task.run()
    assert show_ansi_result(buf.getvalue()) == (
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 0
    assert wrangler.n_updated == 0
    assert wrangler.n_dirty == 0


def test_RepoTask_aborted(monkeypatch):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, quiet=True)
    task = wrangler.repo_task(Repo('xyzzy'))
    task.get_current_branch = lambda dir: 'master'
    task.aborted()
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (aborted)\n'
        "[####################] 1/0"
    )
    assert wrangler.n_repos == 1
    assert wrangler.n_new == 0
    assert wrangler.n_updated == 0
    assert wrangler.n_dirty == 0


def test_RepoTask_verify():
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, verbose=2)
    task = wrangler.repo_task(Repo('xyzzy'))
    task.get_current_branch = lambda dir: 'boo'
    task.get_remote_url = lambda dir: 'root@github.com:test_user/xyzzy'
    task.has_local_changes = lambda dir: True
    task.has_staged_changes = lambda dir: True
    task.has_local_commits = lambda dir: True
    task.verify(task.repo, 'xyzzy')
    # NB: we can see that the output doesn't work right when the terminal
    # width is 80 instead of 100, but I'm not up to fixing it today
    assert show_ansi_result(buf.getvalue(), width=100) == (
        '+ xyzzy (local changes) (staged changes) (local commits)'
        ' (not on master) (wrong remote url)\n'
        '    branch: boo\n'
        '    remote: root@github.com:test_user/xyzzy.git\n'
        '    expected: git@github.com:test_user/xyzzy.git\n'
        '    alternatively: https://github.com/test_user/xyzzy\n'
        "[####################] 1/0"
    )
    assert task.dirty


def test_RepoTask_verify_main():
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, verbose=2)
    task = wrangler.repo_task(Repo('xyzzy', default_branch='main'))
    task.get_current_branch = lambda dir: 'boo'
    task.get_remote_url = lambda dir: 'root@github.com:test_user/xyzzy'
    task.has_local_changes = lambda dir: True
    task.has_staged_changes = lambda dir: True
    task.has_local_commits = lambda dir: True
    task.verify(task.repo, 'xyzzy')
    # NB: we can see that the output doesn't work right when the terminal
    # width is 80 instead of 100, but I'm not up to fixing it today
    assert show_ansi_result(buf.getvalue(), width=100) == (
        '+ xyzzy (local changes) (staged changes) (local commits)'
        ' (not on main) (wrong remote url)\n'
        '    branch: boo\n'
        '    remote: root@github.com:test_user/xyzzy.git\n'
        '    expected: git@github.com:test_user/xyzzy.git\n'
        '    alternatively: https://github.com/test_user/xyzzy\n'
        "[####################] 1/0"
    )
    assert task.dirty


def test_RepoTask_verify_unknown_files():
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, verbose=2)
    task = wrangler.repo_task(Repo('xyzzy'))
    task.get_current_branch = lambda dir: 'master'
    task.get_remote_url = lambda dir: 'git@github.com:test_user/xyzzy'
    task.get_unknown_files = lambda dir: [
        '.coverage', 'tags', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
    ]
    task.verify(task.repo, 'xyzzy')
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (unknown files)\n'
        '    .coverage\n'
        '    tags\n'
        '    a\n'
        '    b\n'
        '    c\n'
        '    d\n'
        '    e\n'
        '    f\n'
        '    g\n'
        '    h\n'
        '    (and 2 more)\n'
        "[####################] 1/0"
    )
    assert task.dirty


def test_RepoTask_branch_name():
    task = ghcloneall.RepoTask({}, None, None, None)
    assert task.branch_name('refs/heads/master') == 'master'
    assert task.branch_name('refs/tags/v0.15') == 'tags/v0.15'


def test_RepoTask_call_status_handling(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.rc = 1
    assert task.call(['git', 'diff', '--quiet']) == 1
    # no failure message should be shown because a non-zero status code is
    # not a failure!
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        "[####################] 1/0"
    )


def test_RepoTask_call_error_handling(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'oh no\n'
    mock_subprocess_Popen.rc = 0
    assert task.call(['git', 'fail', '--please']) == 0
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    oh no\n'
        '    git fail exited with 0\n'
        "[####################] 1/0"
    )


def test_RepoTask_call_error_handling_verbose(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress, verbose=1)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'oh no\n'
    mock_subprocess_Popen.rc = 1
    assert task.call(['git', 'fail', '--please']) == 1
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    oh no\n'
        '    git fail --please exited with 1\n'
        "[####################] 1/0"
    )


def test_RepoTask_check_call_status_handling(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.rc = 1
    task.check_call(['git', 'fail'])
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (failed)\n'
        '    git fail exited with 1\n'
        "[####################] 1/0"
    )


def test_RepoTask_check_call_output_is_shown(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'oh no\n'
    mock_subprocess_Popen.rc = 0
    task.check_call(['git', 'fail', '--please'])
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    oh no\n'
        '    git fail exited with 0\n'
        "[####################] 1/0"
    )


def test_RepoTask_check_call_status_and_output(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'oh no\n'
    mock_subprocess_Popen.rc = 1
    task.check_call(['git', 'fail', '--please'])
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy (failed)\n'
        '    oh no\n'
        '    git fail exited with 1\n'
        "[####################] 1/0"
    )


def test_RepoTask_check_output_error_handling(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'uh oh\n'
    mock_subprocess_Popen.stderr = b'oh no\n'
    mock_subprocess_Popen.rc = 1
    assert task.check_output(['git', 'fail', '--please']) == 'uh oh\n'
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    oh no\n'
        '    git fail exited with 1\n'
        "[####################] 1/0"
    )


def test_RepoTask_check_output_stderr_without_rc(mock_subprocess_Popen):
    buf = StringIO()
    progress = ghcloneall.Progress(stream=buf)
    wrangler = ghcloneall.RepoWrangler(progress=progress)
    task = wrangler.repo_task(Repo('xyzzy'))
    mock_subprocess_Popen.stdout = b'uh oh\n'
    mock_subprocess_Popen.stderr = b'oh no\n'
    mock_subprocess_Popen.rc = 0
    assert task.check_output(['git', 'fail', '--please']) == 'uh oh\n'
    assert show_ansi_result(buf.getvalue()) == (
        '+ xyzzy\n'
        '    oh no\n'
        '    git fail exited with 0\n'
        "[####################] 1/0"
    )


def test_RepoTask_get_current_branch(mock_subprocess_Popen):
    task = ghcloneall.RepoTask({}, None, None, None)
    mock_subprocess_Popen.stdout = b'refs/heads/master\n'
    assert task.get_current_branch('xyzzy') == 'master'


def test_RepoTask_get_remote_url(mock_subprocess_Popen):
    task = ghcloneall.RepoTask({}, None, None, None)
    mock_subprocess_Popen.stdout = b'https://github.com/test_user/xyzzy\n'
    assert task.get_remote_url('xyzzy') == (
        'https://github.com/test_user/xyzzy'
    )


class MockTask:
    def __init__(self, n, output):
        self.n = n
        self.output = output

    def run(self):
        self.output.append(self.n)

    def aborted(self):
        self.output.append(-self.n)


def raise_keyboard_interrupt(*args, **kw):
    raise KeyboardInterrupt()


def test_SequentialJobQueue():
    jobs = []
    with ghcloneall.SequentialJobQueue() as queue:
        queue.add(MockTask(1, jobs))
        queue.add(MockTask(2, jobs))
        queue.add(MockTask(3, jobs))
    assert jobs == [1, 2, 3]


def test_ConcurrentJobQueue():
    done = []
    with ghcloneall.ConcurrentJobQueue(2) as queue:
        queue.add(MockTask(1, done))
        queue.add(MockTask(2, done))
        queue.add(MockTask(3, done))
    assert set(done) == {1, 2, 3}


def test_ConcurrentJobQueue_can_be_interrupted(monkeypatch):
    monkeypatch.setattr(ghcloneall.futures, 'wait', raise_keyboard_interrupt)
    done = []
    with pytest.raises(KeyboardInterrupt):
        with ghcloneall.ConcurrentJobQueue(2) as queue:
            queue.add(MockTask(1, done))
            queue.add(MockTask(2, done))
            queue.add(MockTask(3, done))
    assert set(done) == {1, 2, -3}


def test_main_version(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['ghcloneall', '--version'])
    with pytest.raises(SystemExit):
        ghcloneall.main()


def test_main_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['ghcloneall', '--help'])
    with pytest.raises(SystemExit):
        ghcloneall.main()


def test_main_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(ghcloneall, '_main', raise_keyboard_interrupt)
    ghcloneall.main()


def test_main_missing_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['ghcloneall'])
    with pytest.raises(SystemExit):
        ghcloneall.main()
    assert (
        'Please specify either --user or --organization'
        in capsys.readouterr().err
    )


def test_main_conflicting_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'foo', '--org', 'bar',
    ])
    with pytest.raises(SystemExit):
        ghcloneall.main()
    assert (
        'Please specify either --user or --organization, but not both'
        in capsys.readouterr().err
    )


def test_main_no_org_gists(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--gists', '--org', 'bar',
    ])
    with pytest.raises(SystemExit):
        ghcloneall.main()
    assert (
        'Please specify --user, not --organization, when using --gists'
        in capsys.readouterr().err
    )


def test_main_run_error_handling_with_private_token(
        monkeypatch, mock_requests_get, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--github-token', 'xyzzy',
    ])
    mock_requests_get.set_user('mgedmin')
    with pytest.raises(SystemExit) as ctx:
        ghcloneall.main()
    assert str(ctx.value) == (
        'Failed to fetch https://api.github.com/user/repos'
        '?affiliation=owner&sort=full_name&per_page=100:\n'
        'not found'
    )


def test_main_run_error_handling_no_private_token(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin',
    ])
    with pytest.raises(SystemExit) as ctx:
        ghcloneall.main()
    assert str(ctx.value) == (
        'Failed to fetch https://api.github.com/users/mgedmin/repos'
        '?sort=full_name&per_page=100:\n'
        'not found'
    )


def test_main_run(monkeypatch, mock_requests_get, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--concurrency=1',
    ])
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/mgedmin/repos',
        pages=[
            [
                repo('ghcloneall'),
                repo('experiment', archived=True),
                repo('typo-fix', fork=True),
                repo('xyzzy', private=True, disabled=True),
            ],
        ],
    ))
    ghcloneall.main()
    assert show_ansi_result(capsys.readouterr().out) == (
        '+ ghcloneall (new)\n'
        '1 repositories: 0 updated, 1 new, 0 dirty.'
    )


def test_main_run_with_token(monkeypatch, mock_requests_get, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--concurrency=1',
        '--github-token', 'fake-token',
    ])
    mock_requests_get.set_user('mgedmin')
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/user/repos?affiliation=owner',
        pages=[
            [
                repo('ghcloneall'),
                repo('experiment', archived=True),
                repo('typo-fix', fork=True),
                repo('xyzzy', private=True, disabled=True),
            ],
        ],
    ))
    ghcloneall.main()
    assert show_ansi_result(capsys.readouterr().out) == (
        '+ ghcloneall (new)\n'
        '+ xyzzy (new)\n'
        '2 repositories: 0 updated, 2 new, 0 dirty.'
    )


def test_main_run_with_mismatched_token(monkeypatch, mock_requests_get,
                                        capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'test_user', '--concurrency=1',
        '--github-token', 'fake-token',
    ])
    mock_requests_get.set_user('some-other-user')
    with pytest.raises(SystemExit) as ctx:
        ghcloneall.main()
    assert str(ctx.value) == (
        'The github_user specified (test_user) '
        'does not match the token used.'
    )


def test_main_run_private_without_token(monkeypatch, mock_requests_get,
                                        capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--concurrency=1',
        '--include-private',
    ])
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/mgedmin/repos',
        pages=[
            [
                repo('ghcloneall'),
                repo('experiment', archived=True),
                repo('typo-fix', fork=True),
                repo('xyzzy', private=True, disabled=True),
            ],
        ],
    ))
    ghcloneall.main()
    captured = capsys.readouterr()
    assert show_ansi_result(captured.out) == (
        '+ ghcloneall (new)\n'
        '1 repositories: 0 updated, 1 new, 0 dirty.'
    )
    assert captured.err == (
        'Warning: Listing private repositories requires a GitHub token\n'
    )


def test_main_run_start_from(monkeypatch, mock_requests_get, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--start-from', 'x',
    ])
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/mgedmin/repos',
        pages=[
            [
                repo('ghcloneall'),
                repo('xyzzy'),
            ],
        ],
    ))
    ghcloneall.main()
    assert show_ansi_result(capsys.readouterr().out) == (
        '+ xyzzy (new)\n'
        '1 repositories: 0 updated, 1 new, 0 dirty.'
    )


def test_main_run_gists(monkeypatch, mock_requests_get, capsys):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--user', 'mgedmin', '--gists', '--concurrency=1',
    ])
    mock_requests_get.update(mock_multi_page_api_responses(
        url='https://api.github.com/users/mgedmin/gists',
        extra='',
        pages=[
            [
                gist('1234'),
            ],
        ],
    ))
    ghcloneall.main()
    assert show_ansi_result(capsys.readouterr().out) == (
        '+ 1234 (new)\n'
        '1 repositories: 0 updated, 1 new, 0 dirty.'
    )


@pytest.fixture()
def config_writes_allowed(mock_config_filename, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ghcloneall, 'CONFIG_FILE', '.ghcloneallrc')
    return tmp_path / '.ghcloneallrc'


def test_main_init_dry_run(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--user', 'mgedmin', '--pattern=*.vim',
        '--dry-run',
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Did not write .ghcloneallrc because --dry-run was specified\n'
    )


def test_main_init(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--user', 'mgedmin', '--pattern=*.vim',
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Wrote .ghcloneallrc\n'
    )
    assert config_writes_allowed.read_text() == (
        '[ghcloneall]\n'
        'github_user = mgedmin\n'
        'pattern = *.vim\n'
        '\n'
    )


def test_main_init_gists(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--user', 'mgedmin', '--gists',
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Wrote .ghcloneallrc\n'
    )
    assert config_writes_allowed.read_text() == (
        '[ghcloneall]\n'
        'github_user = mgedmin\n'
        'gists = True\n'
        '\n'
    )


def test_main_init_org(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--org', 'gtimelog',
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Wrote .ghcloneallrc\n'
    )
    assert config_writes_allowed.read_text() == (
        '[ghcloneall]\n'
        'github_org = gtimelog\n'
        '\n'
    )


def test_main_init_org_token(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--org', 'gtimelog', '--github-token',
        'UNITTEST'
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Wrote .ghcloneallrc\n'
    )
    assert config_writes_allowed.read_text() == (
        '[ghcloneall]\n'
        'github_org = gtimelog\n'
        'github_token = UNITTEST\n'
        '\n'
    )


def test_main_init_filter_flags(monkeypatch, capsys, config_writes_allowed):
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall', '--init', '--org', 'gtimelog',
        '--include-forks', '--exclude-private',
        '--exclude-disabled', '--exclude-archived',
    ])
    ghcloneall.main()
    assert capsys.readouterr().out == (
        'Wrote .ghcloneallrc\n'
    )
    assert config_writes_allowed.read_text() == (
        '[ghcloneall]\n'
        'github_org = gtimelog\n'
        'include_forks = True\n'
        'include_archived = False\n'
        'include_private = False\n'
        'include_disabled = False\n'
        '\n'
    )


def test_main_reads_config_file(monkeypatch, capsys, config_writes_allowed):
    config_writes_allowed.write_text(
        u'[ghcloneall]\n'
        u'github_user = mgedmin\n'
        u'github_org = gtimelog\n'
        u'github_token = UNITTEST\n'
        u'gists = False\n'
        u'pattern = *.vim\n'
        u'include_forks = True\n'
        u'include_archived = False\n'
        u'include_private = False\n'
        u'include_disabled = False\n'
        u'\n'
    )
    monkeypatch.setattr(sys, 'argv', [
        'ghcloneall',
    ])
    with pytest.raises(SystemExit):
        ghcloneall.main()
    assert (
        'Please specify either --user or --organization, but not both'
        in capsys.readouterr().err
    )
