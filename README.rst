ghcloneall
==========

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
  - non-master branch checked out
  - committed changes that haven't been pushed to master
  - remote URL pointing to an unexpected location (in --verbose mode only)

You can ask it to not change any files on disk and just look for pending
changes by running ``ghcloneall --dry-run``.  This will also make the
check faster!


Synopsis
--------

Other command-line options::

    $ ghcloneall --help
    usage: ghcloneall [-h] [--version] [-c CONCURRENCY] [-n] [-v]
                      [--start-from REPO] [--organization ORGANIZATION]
                      [--user USER] [--pattern PATTERN] [--init]
                      [--http-cache DBNAME] [--no-http-cache]

    Clone/update all user/org repositories from GitHub.

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      -c CONCURRENCY, --concurrency CONCURRENCY
                            set concurrency level
      -n, --dry-run         don't pull/clone, just print what would be done
      -v, --verbose         perform additional checks
      --start-from REPO     skip all repositories that come before REPO
                            alphabetically
      --organization ORGANIZATION
                            specify the GitHub organization
      --user USER           specify the GitHub user
      --pattern PATTERN     specify repository name pattern to filter
      --init                create a .ghcloneallrc from command-line arguments
      --http-cache DBNAME   cache HTTP requests on disk in an sqlite database
                            (default: .httpcache)
      --no-http-cache       disable HTTP disk caching


Configuration file
------------------

The script looks for ``.ghcloneallrc`` in the current working directory, which
should look like this::

    [ghcloneall]
    # Provide either github_user or github_org, but not both
    # github_org = ZopeFoundation
    github_user = mgedmin
    pattern = *.vim

You can create one with ``ghcloneall --init --{user,org} X [--pattern Y]``.


Tips
----

For best results configure SSH persistence to speed up git pulls -- in your
``~/.ssh/config``::

    Host github.com
    ControlMaster auto
    ControlPersist yes
    ControlPath ~/.ssh/control-%r@%h-%p

It takes about 1 minute to run ``git pull`` on all 339 ZopeFoundation
repos on my laptop with this kind of setup.
