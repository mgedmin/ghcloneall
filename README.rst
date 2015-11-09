Script to clone/update all ZopeFoundation repos from GitHub.

Target audience: ZopeFoundation committers.

Usage::

    git clone https://github.com/mgedmin/cloneall ~/src/cloneall
    mkdir ~/src/zf
    cd ~/src/zf
    ln -s ~/src/cloneall/clone_all_zf_repos.py cloneall.py
    ./cloneall.py

Example output:

.. image:: https://asciinema.org/a/29651.png
   :alt: asciicast
   :width: 582
   :height: 380
   :align: center
   :target: https://asciinema.org/a/29651

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

    $ ./clone_all_zf_repos.py --help
    usage: clone_all_zf_repos.py [-h] [--version] [-c CONCURRENCY] [-n] [-v]
                                 [--start-from REPO] [--organization ORGANIZATION]
                                 [--http-cache DBNAME] [--no-http-cache]

    Clone/update all organization repositories from GitHub

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
      --http-cache DBNAME   cache HTTP requests on disk in an sqlite database
                            (default: .httpcache)
      --no-http-cache       disable HTTP disk caching

For best results configure SSH persistence, to speed up git pulls -- in your
``~/.ssh/config``::

    Host github.com
    ControlMaster auto
    ControlPersist yes
    ControlPath ~/.ssh/control-%r@%h-%p

It takes about 1 minute to run git pull on all 339 zopefoundation repos on my
laptop.
