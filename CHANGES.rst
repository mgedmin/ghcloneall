Changelog
=========


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
