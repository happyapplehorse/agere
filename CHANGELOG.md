# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [Unreleased]

### Added

- Added utils.prompt_template to manage prompt template.
- Added utils.context to manage context.
- Added utils.tools to manage tools.
- async_dispatcher_tools_call_for_openai can receive a to_user_flag to specify the to_user parameter name.
- Added addons.qdrant_vector for RAG.
- Added addons.text_splitter for RAG.

### Fixed

- Fix the drawback where type checking fails to provide correct prompt when using the handler decorator.

### Changed

- The function for creating a generator returned by async_dispatcher_tools_call_for_openai receives its
  parameters changed from "to_user" and "function_call" to "to_user" and "tool_call".


## [0.2.0] - 2024-01-27

### Added

- Added a result attribute to the handler (HandlerCoroutine) and Job object.
- When an exception is encountered, add the exception to the exception attribute of the corresponding handler or Job.
- Added exit_commander method for Job and handler, it can be used to exit commander from within.


## [0.1.3] - 2023-01-05

### Fixed

- Prevent the commander from failing to exit automatically due to an inability to acquire the lock.
- Fixed the bug where the exit code is not passed correctly.
- Fixed the functional defect in the threadsafe-related methods.
- Fixed HandlerCoroutine.add_callback_functions and Job.add_callback_functions error.
- Fixed the issue where the task_node parameter cannot be correctly handle during the initialization of the Callback.

### Changed

- Both 'CommanderAsync.exit' and 'CommanderAsync.wait_for_exit' wait for the commander's thread to finish, not just for the loop to end.
- CommanderAsync.is_empty return True only when '__job_queue', '_children' and '_threadsafe_waiting_tasks' are all empty now.
