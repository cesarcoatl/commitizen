from __future__ import annotations

import inspect
import os
import platform
import shutil

import pytest
from pytest_mock import MockFixture

from commitizen import cmd, exceptions, git
from tests.utils import (
    FakeCommand,
    create_branch,
    create_file_and_commit,
    create_tag,
    switch_branch,
)


@pytest.mark.parametrize("date", ["2020-01-21", "1970-01-01"])
def test_git_tag_date(date: str):
    git_tag = git.GitTag(rev="sha1-code", name="0.0.1", date="2025-05-30")
    git_tag.date = date
    assert git_tag.date == date


def test_git_object_eq():
    git_commit = git.GitCommit(
        rev="sha1-code", title="this is title", body="this is body"
    )
    git_tag = git.GitTag(rev="sha1-code", name="0.0.1", date="2020-01-21")

    assert git_commit == git_tag
    assert git_commit != "sha1-code"


def test_get_tags(mocker: MockFixture):
    tag_str = (
        "v1.0.0---inner_delimiter---333---inner_delimiter---2020-01-20---inner_delimiter---\n"
        "v0.5.0---inner_delimiter---222---inner_delimiter---2020-01-17---inner_delimiter---\n"
        "v0.0.1---inner_delimiter---111---inner_delimiter---2020-01-17---inner_delimiter---\n"
    )
    mocker.patch("commitizen.cmd.run", return_value=FakeCommand(out=tag_str))

    git_tags = git.get_tags()
    latest_git_tag = git_tags[0]
    assert latest_git_tag.rev == "333"
    assert latest_git_tag.name == "v1.0.0"
    assert latest_git_tag.date == "2020-01-20"

    mocker.patch(
        "commitizen.cmd.run", return_value=FakeCommand(out="", err="No tag available")
    )
    assert git.get_tags() == []


def test_get_reachable_tags(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        create_file_and_commit("Initial state")
        create_tag("1.0.0")
        # create develop
        create_branch("develop")
        switch_branch("develop")

        # add a feature to develop
        create_file_and_commit("develop")
        create_tag("1.1.0b0")

        # create staging
        switch_branch("master")
        create_file_and_commit("master")
        create_tag("1.0.1")

        tags = git.get_tags(reachable_only=True)
        tag_names = set([t.name for t in tags])
        # 1.1.0b0 is not present
        assert tag_names == {"1.0.0", "1.0.1"}


@pytest.mark.parametrize("locale", ["en_US", "fr_FR"])
def test_get_reachable_tags_with_commits(
    tmp_commitizen_project, locale: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("LANG", f"{locale}.UTF-8")
    monkeypatch.setenv("LANGUAGE", f"{locale}.UTF-8")
    monkeypatch.setenv("LC_ALL", f"{locale}.UTF-8")
    with tmp_commitizen_project.as_cwd():
        assert git.get_tags(reachable_only=True) == []


def test_get_tag_names(mocker: MockFixture):
    tag_str = "v1.0.0\nv0.5.0\nv0.0.1\n"
    mocker.patch("commitizen.cmd.run", return_value=FakeCommand(out=tag_str))

    assert git.get_tag_names() == ["v1.0.0", "v0.5.0", "v0.0.1"]

    mocker.patch(
        "commitizen.cmd.run", return_value=FakeCommand(out="", err="No tag available")
    )
    assert git.get_tag_names() == []


def test_git_message_with_empty_body():
    commit_title = "Some Title"
    commit = git.GitCommit("test_rev", "Some Title", body="")

    assert commit.message == commit_title


@pytest.mark.usefixtures("tmp_commitizen_project")
def test_get_log_as_str_list_empty():
    """ensure an exception or empty list in an empty project"""
    try:
        gitlog = git._get_log_as_str_list(start=None, end="HEAD", args="")
    except exceptions.GitCommandError:
        return
    assert len(gitlog) == 0, "list should be empty if no assert"


@pytest.mark.usefixtures("tmp_commitizen_project")
def test_get_commits():
    create_file_and_commit("feat(users): add username")
    create_file_and_commit("fix: username exception")
    commits = git.get_commits()
    assert len(commits) == 2


@pytest.mark.usefixtures("tmp_commitizen_project")
def test_get_commits_author_and_email():
    create_file_and_commit("fix: username exception")
    commit = git.get_commits()[0]

    assert commit.author != ""
    assert "@" in commit.author_email


def test_get_commits_without_email(mocker: MockFixture):
    raw_commit = (
        "a515bb8f71c403f6f7d1c17b9d8ebf2ce3959395\n"
        "95bbfc703eb99cb49ba0d6ffd8469911303dbe63 12d3b4bdaa996ea7067a07660bb5df4772297bdd\n"
        "\n"
        "user name\n"
        "\n"
        "----------commit-delimiter----------\n"
        "12d3b4bdaa996ea7067a07660bb5df4772297bdd\n"
        "de33bc5070de19600f2f00262b3c15efea762408\n"
        "feat(users): add username\n"
        "user name\n"
        "\n"
        "----------commit-delimiter----------\n"
    )
    mocker.patch("commitizen.cmd.run", return_value=FakeCommand(out=raw_commit))

    commits = git.get_commits()

    assert commits[0].author == "user name"
    assert commits[1].author == "user name"

    assert commits[0].author_email == ""
    assert commits[1].author_email == ""

    assert commits[0].title == ""
    assert commits[1].title == "feat(users): add username"


def test_get_commits_without_breakline_in_each_commit(mocker: MockFixture):
    raw_commit = (
        "ae9ba6fc5526cf478f52ef901418d85505109744\n"
        "ff2f56ca844de72a9d59590831087bf5a97bac84\n"
        "bump: version 2.13.0 → 2.14.0\n"
        "GitHub Action\n"
        "action@github.com\n"
        "----------commit-delimiter----------\n"
        "ff2f56ca844de72a9d59590831087bf5a97bac84\n"
        "b4dc83284dc8c9729032a774a037df1d1f2397d5 20a54bf1b82cd7b573351db4d1e8814dd0be205d\n"
        "Merge pull request #332 from cliles/feature/271-redux\n"
        "User\n"
        "user@email.com\n"
        "Feature/271 redux----------commit-delimiter----------\n"
        "20a54bf1b82cd7b573351db4d1e8814dd0be205d\n"
        "658f38c3fe832cdab63ed4fb1f7b3a0969a583be\n"
        "feat(#271): enable creation of annotated tags when bumping\n"
        "User 2\n"
        "user@email.edu\n"
        "----------commit-delimiter----------\n"
    )
    mocker.patch("commitizen.cmd.run", return_value=FakeCommand(out=raw_commit))

    commits = git.get_commits()

    assert commits[0].author == "GitHub Action"
    assert commits[1].author == "User"
    assert commits[2].author == "User 2"

    assert commits[0].author_email == "action@github.com"
    assert commits[1].author_email == "user@email.com"
    assert commits[2].author_email == "user@email.edu"

    assert commits[0].title == "bump: version 2.13.0 → 2.14.0"
    assert commits[1].title == "Merge pull request #332 from cliles/feature/271-redux"
    assert (
        commits[2].title == "feat(#271): enable creation of annotated tags when bumping"
    )


def test_get_commits_with_and_without_parents(mocker: MockFixture):
    raw_commit = (
        "4206e661bacf9643373255965f34bbdb382cb2b9\n"
        "ae9ba6fc5526cf478f52ef901418d85505109744 bf8479e7aa1a5b9d2f491b79e3a4d4015519903e\n"
        "Merge pull request from someone\n"
        "Maintainer\n"
        "maintainer@email.com\n"
        "This is a much needed feature----------commit-delimiter----------\n"
        "ae9ba6fc5526cf478f52ef901418d85505109744\n"
        "ff2f56ca844de72a9d59590831087bf5a97bac84\n"
        "Release 0.1.0\n"
        "GitHub Action\n"
        "action@github.com\n"
        "----------commit-delimiter----------\n"
        "ff2f56ca844de72a9d59590831087bf5a97bac84\n"
        "\n"
        "Initial commit\n"
        "User\n"
        "user@email.com\n"
        "----------commit-delimiter----------\n"
    )
    mocker.patch("commitizen.cmd.run", return_value=FakeCommand(out=raw_commit))

    commits = git.get_commits()

    assert commits[0].author == "Maintainer"
    assert commits[1].author == "GitHub Action"
    assert commits[2].author == "User"

    assert commits[0].author_email == "maintainer@email.com"
    assert commits[1].author_email == "action@github.com"
    assert commits[2].author_email == "user@email.com"

    assert commits[0].title == "Merge pull request from someone"
    assert commits[1].title == "Release 0.1.0"
    assert commits[2].title == "Initial commit"

    assert commits[0].body == "This is a much needed feature"
    assert commits[1].body == ""
    assert commits[2].body == ""

    assert commits[0].parents == [
        "ae9ba6fc5526cf478f52ef901418d85505109744",
        "bf8479e7aa1a5b9d2f491b79e3a4d4015519903e",
    ]
    assert commits[1].parents == ["ff2f56ca844de72a9d59590831087bf5a97bac84"]
    assert commits[2].parents == []


def test_get_commits_with_signature():
    config_file = ".git/config"
    config_backup = ".git/config.bak"
    shutil.copy(config_file, config_backup)

    try:
        # temporarily turn on --show-signature
        cmd.run("git config log.showsignature true")

        # retrieve a commit that we know has a signature
        commit = git.get_commits(
            start="bec20ebf433f2281c70f1eb4b0b6a1d0ed83e9b2",
            end="9eae518235d051f145807ddf971ceb79ad49953a",
        )[0]

        assert commit.title.startswith("fix")
    finally:
        # restore the repo's original config
        shutil.move(config_backup, config_file)


def test_get_tag_names_has_correct_arrow_annotation():
    arrow_annotation = inspect.getfullargspec(git.get_tag_names).annotations["return"]

    assert arrow_annotation == "list[str]"


def test_get_latest_tag_name(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        tag_name = git.get_latest_tag_name()
        assert tag_name is None

        create_file_and_commit("feat(test): test")
        cmd.run("git tag 1.0")
        tag_name = git.get_latest_tag_name()
        assert tag_name == "1.0"


def test_is_staging_clean_when_adding_file(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        assert git.is_staging_clean() is True

        cmd.run("touch test_file")

        assert git.is_staging_clean() is True

        cmd.run("git add test_file")

        assert git.is_staging_clean() is False


def test_is_staging_clean_when_updating_file(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        assert git.is_staging_clean() is True

        cmd.run("touch test_file")
        cmd.run("git add test_file")
        if os.name == "nt":
            cmd.run('git commit -m "add test_file"')
        else:
            cmd.run("git commit -m 'add test_file'")
        cmd.run("echo 'test' > test_file")

        assert git.is_staging_clean() is True

        cmd.run("git add test_file")

        assert git.is_staging_clean() is False


def test_get_eol_for_open(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        assert git.EOLType.for_open() == os.linesep

        cmd.run("git config core.eol lf")
        assert git.EOLType.for_open() == "\n"

        cmd.run("git config core.eol crlf")
        assert git.EOLType.for_open() == "\r\n"

        cmd.run("git config core.eol native")
        assert git.EOLType.for_open() == os.linesep


def test_get_core_editor(mocker):
    mocker.patch.dict(os.environ, {"GIT_EDITOR": "nano"})
    assert git.get_core_editor() == "nano"

    mocker.patch.dict(os.environ, clear=True)
    mocker.patch(
        "commitizen.cmd.run",
        return_value=cmd.Command(
            out="vim", err="", stdout=b"", stderr=b"", return_code=0
        ),
    )
    assert git.get_core_editor() == "vim"

    mocker.patch(
        "commitizen.cmd.run",
        return_value=cmd.Command(out="", err="", stdout=b"", stderr=b"", return_code=1),
    )
    assert git.get_core_editor() is None


def test_create_tag_with_message(tmp_commitizen_project):
    with tmp_commitizen_project.as_cwd():
        create_file_and_commit("feat(test): test")
        tag_name = "1.0"
        tag_message = "test message"
        create_tag(tag_name, tag_message)
        assert git.get_latest_tag_name() == tag_name
        assert git.get_tag_message(tag_name) == (
            tag_message if platform.system() != "Windows" else f"'{tag_message}'"
        )


@pytest.mark.parametrize(
    "file_path,expected_cmd",
    [
        (
            "/tmp/temp file",
            'git commit --signoff -F "/tmp/temp file"',
        ),
        (
            "/tmp dir/temp file",
            'git commit --signoff -F "/tmp dir/temp file"',
        ),
        (
            "/tmp/tempfile",
            'git commit --signoff -F "/tmp/tempfile"',
        ),
    ],
    ids=[
        "File contains spaces",
        "Path contains spaces",
        "Path does not contain spaces",
    ],
)
def test_commit_with_spaces_in_path(mocker, file_path, expected_cmd):
    mock_run = mocker.patch("commitizen.cmd.run", return_value=FakeCommand())
    mock_unlink = mocker.patch("os.unlink")
    mock_temp_file = mocker.patch("commitizen.git.NamedTemporaryFile")
    mock_temp_file.return_value.name = file_path

    git.commit("feat: new feature", "--signoff")

    mock_run.assert_called_once_with(expected_cmd)
    mock_unlink.assert_called_once_with(file_path)


def test_get_filenames_in_commit_error(mocker: MockFixture):
    """Test that GitCommandError is raised when git command fails."""
    mocker.patch(
        "commitizen.cmd.run",
        return_value=FakeCommand(out="", err="fatal: bad object HEAD", return_code=1),
    )
    with pytest.raises(exceptions.GitCommandError) as excinfo:
        git.get_filenames_in_commit()
    assert str(excinfo.value) == "fatal: bad object HEAD"


def test_git_commit_from_rev_and_commit():
    # Test data with all fields populated
    rev_and_commit = (
        "abc123\n"  # rev
        "def456 ghi789\n"  # parents
        "feat: add new feature\n"  # title
        "John Doe\n"  # author
        "john@example.com\n"  # author_email
        "This is a detailed description\n"  # body
        "of the new feature\n"
        "with multiple lines"
    )

    commit = git.GitCommit.from_rev_and_commit(rev_and_commit)

    assert commit.rev == "abc123"
    assert commit.title == "feat: add new feature"
    assert (
        commit.body
        == "This is a detailed description\nof the new feature\nwith multiple lines"
    )
    assert commit.author == "John Doe"
    assert commit.author_email == "john@example.com"
    assert commit.parents == ["def456", "ghi789"]

    # Test with minimal data
    minimal_commit = (
        "abc123\n"  # rev
        "\n"  # no parents
        "feat: minimal commit\n"  # title
        "John Doe\n"  # author
        "john@example.com\n"  # author_email
    )

    commit = git.GitCommit.from_rev_and_commit(minimal_commit)

    assert commit.rev == "abc123"
    assert commit.title == "feat: minimal commit"
    assert commit.body == ""
    assert commit.author == "John Doe"
    assert commit.author_email == "john@example.com"
    assert commit.parents == []


@pytest.mark.parametrize(
    "os_name,committer_date,expected_cmd",
    [
        (
            "nt",
            "2024-03-20",
            'cmd /v /c "set GIT_COMMITTER_DATE=2024-03-20&& git commit  -F "temp.txt""',
        ),
        (
            "posix",
            "2024-03-20",
            'GIT_COMMITTER_DATE=2024-03-20 git commit  -F "temp.txt"',
        ),
        ("nt", None, 'git commit  -F "temp.txt"'),
        ("posix", None, 'git commit  -F "temp.txt"'),
    ],
)
def test_create_commit_cmd_string(mocker, os_name, committer_date, expected_cmd):
    """Test the OS-specific behavior of _create_commit_cmd_string"""
    mocker.patch("os.name", os_name)
    result = git._create_commit_cmd_string("", committer_date, "temp.txt")
    assert result == expected_cmd
