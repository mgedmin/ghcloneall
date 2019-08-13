import sys
import pytest
import ghcloneall


def test_main_version(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['ghcloneall', '--version'])
    with pytest.raises(SystemExit):
        ghcloneall.main()


def test_main_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['ghcloneall', '--help'])
    with pytest.raises(SystemExit):
        ghcloneall.main()
