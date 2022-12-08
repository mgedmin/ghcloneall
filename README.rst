ghcloneall
==========

.. image:: https://github.com/mgedmin/ghcloneall/workflows/build/badge.svg?branch=master
    :target: https://github.com/mgedmin/ghcloneall/actions

.. image:: https://ci.appveyor.com/api/projects/status/github/mgedmin/ghcloneall?branch=master&svg=true
    :target: https://ci.appveyor.com/project/mgedmin/ghcloneall


It's a script to clone/update all repos for a user/organization from GitHub.

Target audience: maintainers of large collections of projects (for example,
ZopeFoundation members).


Usage examples
--------------

First ``pip install ghcloneall``.

Clone all mgedmin's vim plugins::

    mkdir ~/src/vim-plugins
    cd ~/src/vim-plugins
    ghcloneall --init --user mgedmin --pattern '*.vim'
    ghcloneall

Clone all mgedmin's gists::

    mkdir ~/src/gists
    cd ~/src/gists
    ghcloneall --init --user mgedmin --gists
    ghcloneall

Clone all ZopeFoundation repositories::

    mkdir ~/src/zf
    cd ~/src/zf
    ghcloneall --init --org ZopeFoundation
    ghcloneall

Here's a screencast of the above (running a slightly older version so the
script name differs):

.. image:: https://asciinema.org/a/29651.png
   :alt: asciicast
   :width: 582
   :height: 380
   :align: center
   :target: https://asciinema.org/a/29651


Details
-------

What it does:

- clones repositories you don't have locally
- pulls changes for repositories you already have locally
- warns you about local changes and other unexpected situations:

  - unknown files in the tree (in --verbose mode only)
  - staged but not committed changes
  - uncommitted (and unstaged changes)
  - non-default branch checked out
  - committed changes that haven't been pushed to default branch
  - remote URL pointing to an unexpected location (in --verbose mode only)

You can ask it to not change any files on disk and just look for pending
changes by running ``ghcloneall --dry-run``.  This will also make the
check faster!


Synopsis
--------

.. [[[cog
..   import cog, subprocess, textwrap, os
..   os.environ['COLUMNS'] = '80'  # consistent line wrapping
..   helptext = subprocess.run(['ghcloneall', '--help'],
..                             capture_output=True, text=True).stdout
..   cog.outl('\nOther command-line options::\n')
..   cog.outl('    $ ghcloneall --help')
..   cog.outl(textwrap.indent(helptext, '    '))
.. ]]]

Other command-line options::

    $ ghcloneall --help
    usage: ghcloneall [-h] [--version] [-c CONCURRENCY] [-n] [-q] [-v]
                      [--start-from REPO] [--organization ORGANIZATION]
                      [--user USER] [--github-token GITHUB_TOKEN] [--gists]
                      [--repositories] [--pattern PATTERN] [--include-forks]
                      [--exclude-forks] [--include-archived] [--exclude-archived]
                      [--include-private] [--exclude-private] [--include-disabled]
                      [--exclude-disabled] [--init] [--http-cache DBNAME]
                      [--no-http-cache]

    Clone/update all user/org repositories from GitHub.

    options:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      -c CONCURRENCY, --concurrency CONCURRENCY
                            set concurrency level (default: 4)
      -n, --dry-run         don't pull/clone, just print what would be done
      -q, --quiet           terser output
      -v, --verbose         perform additional checks
      --start-from REPO     skip all repositories that come before REPO
                            alphabetically
      --organization ORGANIZATION
                            specify the GitHub organization
      --user USER           specify the GitHub user
      --github-token GITHUB_TOKEN
                            specify the GitHub token
      --gists               clone user's gists
      --repositories        clone user's or organisation's repositories (default)
      --pattern PATTERN     specify repository name glob pattern to filter
      --include-forks       include repositories forked from other users/orgs
      --exclude-forks       exclude repositories forked from other users/orgs
                            (default)
      --include-archived    include archived repositories
      --exclude-archived    exclude archived repositories (default)
      --include-private     include private repositories (default when a github
                            token is provided)
      --exclude-private     exclude private repositories
      --include-disabled    include disabled repositories (default)
      --exclude-disabled    exclude disabled repositories
      --init                create a .ghcloneallrc from command-line arguments
      --http-cache DBNAME   cache HTTP requests on disk in an sqlite database for
                            5 minutes (default: .httpcache)
      --no-http-cache       disable HTTP disk caching

.. [[[end]]]


Configuration file
------------------

The script looks for ``.ghcloneallrc`` in the current working directory, which
should look like this::

    [ghcloneall]
    # Provide either github_user or github_org, but not both
    # github_org = ZopeFoundation
    github_user = mgedmin
    pattern = *.vim
    # Provide github token for authentication
    # github_token = <my-github-token>
    # You can also uncomment and change these if you wish
    # gists = False
    # include_forks = False
    # include_archived = False
    # Listing private repositories requires a valid github_token
    # include_private = True
    # include_disabled = True

You can create one with ``ghcloneall --init --{user,org} X [--pattern Y]
[--{include,exclude}-{forks,archived,private,disabled}] [--gists|--repos]``.


Tips
----

For best results configure SSH persistence to speed up git pulls -- in your
``~/.ssh/config``::

    Host github.com
    ControlMaster auto
    ControlPersist yes
    ControlPath ~/.ssh/control-%r@%h-%p

It takes about 80 seconds to run ``git pull`` on all 382 ZopeFoundation
repos on my laptop with this kind of setup.
