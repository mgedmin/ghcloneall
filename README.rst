Script to clone/update all repos for a user/organization from GitHub.

Target audience: maintainers of large collections of projects (for example,
ZopeFoundation members).

Usage::

    git clone https://github.com/mgedmin/cloneall ~/src/cloneall
    mkdir ~/src/zf
    cd ~/src/zf
    ln -s ~/src/cloneall/cloneall.py cloneall.py
    ./cloneall.py --org ZopeFoundation

Example output:

.. image:: https://asciinema.org/a/29651.png
   :alt: asciicast
   :width: 582
   :height: 380
   :align: center
   :target: https://asciinema.org/a/29651

Another example::

   mkdir ~/src/vim-plugins
   cd ~/src/vim-plugins
   cloneall.py --user mgedmin --pattern '*.vim'

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

You can speed up the checks for local unpublished changes by running
``./cloneall.py -n``: this will skip the ``git pull``/``git clone``.

Other command-line options::

    $ ./cloneall.py --help
    usage: cloneall.py [-h] [--version] [-c CONCURRENCY] [-n] [-v]
                       [--start-from REPO] [--organization ORGANIZATION]
                       [--user USER] [--pattern PATTERN] [--http-cache DBNAME]
                       [--no-http-cache]

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
                            specify the GitHub organization (default:
                            ZopeFoundation)
      --user USER           specify the GitHub user (default: None)
      --pattern PATTERN     specify repository name pattern (default: *)
      --http-cache DBNAME   cache HTTP requests on disk in an sqlite database
                            (default: .httpcache)
      --no-http-cache       disable HTTP disk caching

For best results configure SSH persistence, to speed up git pulls -- in your
``~/.ssh/config``::

    Host github.com
    ControlMaster auto
    ControlPersist yes
    ControlPath ~/.ssh/control-%r@%h-%p

It takes about 1 minute to run ``git pull`` on all 339 ZopeFoundation
repos on my laptop.
