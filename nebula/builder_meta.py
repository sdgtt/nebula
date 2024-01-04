"""This module contains functions to check builder outputs for various data points."""

import os

def hdl_passed_timing_report(report_filename):
    """Check if the passed timing report contains any failing paths.

    Args:
        report_filename (str): The path to the timing report.

    Returns:
        bool: True if the timing report contains no failing paths, False otherwise.
    """
    if not os.path.isfile(report_filename):
        raise ValueError(f"The passed report filename does not exist: {report_filename}")
    with open(report_filename, "r") as f:
        report = f.read()
    return "All user specified timing constraints are met." in report

def get_git_repo_info(repo_root_folder):
    """Get the git repository information for the passed repository.

    Args:
        repo_root_folder (str): The path to the root folder of the git repository.

    Returns:
        dict: A dictionary containing the git repository information.
    """
    if not os.path.isdir(repo_root_folder):
        raise ValueError(f"The passed repo root folder does not exist: {repo_root_folder}")
    cwd = os.getcwd()
    os.chdir(repo_root_folder)
    commit_hash = os.popen("git rev-parse HEAD").read().strip()
    commit_date = os.popen("git show -s --format=%ci").read().strip()
    committer = os.popen("git show -s --format=%cn").read().strip()
    committer_email = os.popen("git show -s --format=%ce").read().strip()
    commit_message = os.popen("git show -s --format=%s").read().strip()
    dirty = os.popen("git diff-index --quiet HEAD --").read().strip()
    repo_remote = os.popen("git remote get-url origin").read().strip()
    os.chdir(cwd)
    return {
        "commit_hash": commit_hash,
        "commit_date": commit_date,
        "committer": committer,
        "committer_email": committer_email,
        "commit_message": commit_message,
        "dirty": dirty,
        "repo_remote": repo_remote,
    }
