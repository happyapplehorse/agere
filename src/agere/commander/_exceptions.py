class TaskNodeException(Exception):
    """Base class for exceptions related to TaskNode."""


class CommanderException(Exception):
    """Base class for exceptions related to Commander."""


class JobException(TaskNodeException):
    """Base class for exceptions related to Job."""


class HandlerException(TaskNodeException):
    """Base class for exceptions related to Handler."""


class NoCommanderError(TaskNodeException):
    """Raised when the commander is used in a TaskNode but the commander attribute has not been set."""


class AttributeNotSetError(TaskNodeException):
    """Raised when attempting to use an attribute that has not been set."""


class CommanderNotRunError(CommanderException):
    """Raised when commander should be running but isn't."""


class CommanderAlreadyRunningError(CommanderException):
    """Raised when the commander is found to be running when it should not be."""


class NotTaskerError(JobException):
    """Raised when a Job's task method is not a Tasker."""


class NotHandlerError(HandlerException):
    """Raised when a non-handler object is called as if it were a handler."""
