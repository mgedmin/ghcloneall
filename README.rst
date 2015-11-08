Script to clone/update all ZopeFoundation repos from GitHub.

Target audience: ZopeFoundation committers.

Usage::

    git clone https://github.com/mgedmin/cloneall ~/src/cloneall
    mkdir ~/src/zf
    cd ~/src/zf
    ln -s ~/src/cloneall/clone_all_zf_repos.py cloneall.py
    ./cloneall.py

Example output:

.. image:: https://asciinema.org/a/29580.png
   :alt: asciicast
   :width: 582
   :height: 380
   :align: center
   :target: https://asciinema.org/a/29580

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

For best results configure SSH persistence, to speed up git pulls -- in your
``~/.ssh/config``:

    Host github.com
    ControlMaster auto
    ControlPersist yes
    ControlPath ~/.ssh/control-%r@%h-%p

It takes about 3 minutes to run git pull on all 339 zopefoundation repos on my
laptop.
