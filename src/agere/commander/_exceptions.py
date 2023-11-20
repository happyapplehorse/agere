class CommanderException(Exception):
    ...


class NoCommanderError(CommanderException):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Commander not found in {self.job}."


class CommanderNotRunError(CommanderException):
    def __init__(self, commander):
        self.commander = commander
    
    def __str__(self):
        return f"Commander is not running, commander: {self.commander}."


class CommanderAlreadyRunningError(CommanderException):
    def __init__(self, commander):
        self.commander = commander
    
    def __str__(self):
        return f"Commander already is running, commander: {self.commander}"


class NotTaskerError(CommanderException):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Task method of {self.job} is not a Tasker."


class NotHandlerError(CommanderException):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Object is not a Handler called in {self.job}."


class AttributeNotSetError(CommanderException):
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    
    def __str__(self):
        return f"The {self.attr} attribute of {self.obj} has not been set yet."
