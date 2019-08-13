import re
import sys

try:
    from cStringIO import StringIO
except ImportError:  # pragma: PY3
    from io import StringIO

import pytest
import requests

import ghcloneall


class MockResponse:

    def __init__(self, status_code=200, json=None, headers=()):
        self.status_code = status_code
        self.headers = {
            'content-type': 'application/json'
        }
        self.headers.update(headers)
        self._json = json or {'json': 'data'}

    def json(self):
        return self._json


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
    pattern = '|'.join(re.escape(s) for s in replacements)
    return re.sub(pattern, lambda m: replacements[m.group(0)], text)


def compare(actual, expected):
    assert show_ansi(actual) == show_ansi(expected)


def test_get_json_and_headers(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda url: MockResponse())
    url = 'https://github.example.com/api'
    data, headers = ghcloneall.get_json_and_headers(url)
    assert data == {'json': 'data'}
    assert headers == {'content-type': 'application/json'}


def test_get_json_and_headers_failure(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda url: MockResponse(
        status_code=400, json={'message': 'this request is baaad'}))
    url = 'https://github.example.com/api'
    with pytest.raises(ghcloneall.Error):
        ghcloneall.get_json_and_headers(url)


def test_get_github_list(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda url: {
        'https://github.example.com/api?per_page=100': MockResponse(
            json=[{'item': 1}, {'item': 2}],
            headers={
                'Link': (
                    '<https://github.example.com/api?page=2&per_page=100>;'
                    ' rel="next"'
                ),
            }),
        'https://github.example.com/api?page=2&per_page=100': MockResponse(
            json=[{'item': 3}, {'item': 4}],
            headers={
                'Link': (
                    '<https://github.example.com/api?page=3&per_page=100>;'
                    ' rel="next"'
                ),
            }),
        'https://github.example.com/api?page=3&per_page=100': MockResponse(
            json=[{'item': 5}]),
    }.get(url, MockResponse(status_code=404, json={'message': 'no'})))
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
