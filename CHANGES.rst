Changelog
=========


1.12.0 (2024-10-09)
-------------------

- Add support for Python 3.12 and 3.13.
- Drop support for Python 2.7.


1.11.0 (2022-10-27)
-------------------

- Add support for Python 3.10 and 3.11.
- Drop support for Python 3.6.
- Fix ``ghcloneall --user ... --github-token ... --include-private`` not
  including any private repositories (GH: #16).


1.10.1 (2021-05-26)
-------------------

- When determining if a repository is dirty, use the repository's
  configured default branch from GitHub instead of assuming that the
  default is "master".


1.10.0 (2021-04-10)
-------------------

- Allow authentication with GitHub token.
- Depend on requests-cache < 0.6 on Python 2.7.
- Add support for Python 3.9.
- Drop support for Python 3.5.


1.9.2 (2019-10-15)
------------------

- Add support for Python 3.8.


1.9.1 (2019-10-07)
------------------

- Reuse HTTP connections for GitHub API requests.


1.9.0 (2019-09-06)
------------------

- Can now clone all user's gists.
- Command line args: --gists, --repos.


1.8.0 (2019-08-28)
------------------

- Skip forks and archived repositories by default.
- Command-line args: --include-forks, --exclude-forks.
- Command-line args: --include-archived, --exclude-archived.
- Command-line args: --include-private, --exclude-private.
- Command-line args: --include-disabled, --exclude-disabled.
- Use a custom User-Agent header when talking to GitHub.


1.7.1 (2019-08-14)
------------------

- Drop support for Python 3.3 and 3.4.
- Add a test suite.
- Fix AttributeError: 'str' object has no attribute 'format_map' on Python 2.


1.7.0 (2018-12-19)
------------------

- Command line args: -q, --quiet
- Fix display corruption on ^C


1.6.1 (2018-10-19)
------------------

- Fix TypeError: get() got an unexpected keyword argument 'fallback' on
  Python 2.


1.6 (2016-12-29)
----------------

- Comprehensive rebranding:

  - Rename the GitHub repository to https://github.com/mgedmin/ghcloneall
  - Rename ``cloneall.py`` to ``ghcloneall.py``
  - Rename the config file to ``.ghcloneallrc``, and rename the config
    section to ``[ghcloneall]``.

- Don't print tracebacks on ^C (this regressed in 1.5).


1.5 (2016-12-29)
----------------

- Released to PyPI as ``ghcloneall``
- Added Python 2.7 support


1.4 (2016-12-28)
----------------

- Command line args: --user, --pattern, --init
- Load (some) options from a ``.cloneallrc``
- Stop using ``--organization=ZopeFoundation`` by default, require an
  explicit option (or config file)
- Rename clone_all_zf_repos.py to cloneall.py


1.3 (2016-12-28)
----------------

- Command line args: -c
- Show progress while fetching the list of repositories from GitHub
- Update repositories concurrently by default
- Highlight items in progress
- Highlight failed items in red
- Tweak progress bar style from ``[===  ]`` to ``[###..]``
- Clear the progress bar on ^C
- Handle git errors nicely
- Bugfix: -vv could fail with NameError if unknown files were present in a
  working tree
- Bugfix: correctly show progress when using --start-from
- Bugfix: script would hang (for 10 minutes) if you didn't already have an
  SSH control master process running
- Bugfix: --dry-run didn't show which repos were new


1.2 (2016-11-09)
----------------

- Command line args: --dry-run, --verbose
- Cache HTTP responses on disk for 10 minutes to avoid GitHub API rate limits
- Report about forgotten uncommitted and staged changes
- Warn about local (unpushed) commits too
- Warn about other branches being checked out
- Default to SSH URLs again (faster when using SSH's ControlPersist)


1.1 (2015-11-07)
----------------

- Command line args: --version, --start-from, --organization
- Output formatting: shorter repository names, totals at the end
- Use ANSI colors to indicate changes
- Don't print tracebacks on ^C
- Default to HTTPS URLs


1.0 (2015-11-07)
----------------

- Moved from a gist to a proper GitHub repository.
