# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.1.3] - 2023-01-05

### Fixed

- Prevent the commander from failing to exit automatically due to an inability to acquire the lock
- Fixed the bug where the exit code is not passed correctly
- Fixed the functional defect in the threadsafe-related methods 

### Changed

- Both 'CommanderAsync.exit' and 'CommanderAsync.wait_for_exit' wait for the commander's thread to finish, not just for the loop to end
- CommanderAsync.is_empty return True only when '__job_queue', '_children' and '_threadsafe_waiting_tasks' are all empty now
