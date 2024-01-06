from __future__ import annotations
import asyncio
import itertools
import logging
import sys
import threading
import weakref
from abc import ABCMeta, abstractmethod
from asyncio import AbstractEventLoop, Task
from functools import wraps
from inspect import iscoroutinefunction
from typing import (
    TypeVar,
    Generic,
    Coroutine,
    Sequence,
    Iterable,
    Literal,
    Final,
    TypedDict,
    Callable,
    cast,
)

from ._exceptions import (
    AttributeNotSetError,
    NotHandlerError,
    NotTaskerError,
    CommanderNotRunError,
    CommanderAlreadyRunningError,
)
from ._null_logger import get_null_logger


PASS_WORD: Final[str] = "I assure all time-consuming tasks are delegated externally."
CallbackType = Literal["at_job_start", "at_handler_start", "at_exception", "at_terminate", "at_handler_end", "at_job_end", "at_commander_end"]


class TaskNode:
    def __init__(self):
        self._id: int | str | None = None
        self._commander: CommanderAsync | None = None
        self._parent: TaskNode | None | Literal["Null"] = None
        self._children: list = [self]
        self._callback: Callback | None = None
        self._state: Literal["PENDING", "ACTIVE", "TERMINATED", "EXCEPTION", "COMPLETED"] = "PENDING"
    
    def add_child(self, child: TaskNode) -> None:
        """Add a tasknode as child of this tasknode."""
        self._children.append(child)
        child._parent = self
        child._state = "ACTIVE"
    
    async def del_child(self, child: TaskNode) -> None:
        """Remove the tasknode from the children list and do the 'done check'."""
        try:
            self._children.remove(child)
        except ValueError:
            # _children may have be cleared by terminated operation.
            # Since no deletion poeration was performed, there's nothing to do.
            return
        if not self._children:
            await self._do_at_done()
            if self._state not in ["TERMINATED", "EXCEPTION"]:
                self._state = "COMPLETED"
            parent = self.parent
            if parent != "Null":
                await parent.del_child(self)

    async def _do_at_done(self):
        """This method is automatically called when the tasknode is completed."""
        ...

    @property
    def id(self) -> int | str | None:
        """The ID of this node.

        Each node is automatically assigned an integer ID by the commander after being scheduled.
        This integer ID is generated from an auto-increment counter.
        If a node has been manually assigned an ID,
        the commander will not automatically set an ID for it again.
        To avoid duplication with IDs set automatically,
        a string should be used as the ID value when manually setting the ID for a node.
        """
        if self._id is None:
            raise AttributeNotSetError(f"The _id attribute of {self!r} has not been set yet.")
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """Set ID for this node.

        To avoid duplication with IDs set automatically,
        a string should be used as the ID value when manually setting the ID for a node.
        """
        self._id = value

    @property
    def commander(self) -> CommanderAsync:
        """The commander object that manages this node."""
        if self._commander is None:
            raise AttributeNotSetError(f"The _commander attribute of {self!r} has not been set yet.")
        return self._commander

    @property
    def parent(self) -> TaskNode | Literal["Null"]:
        """The parent node of this node."""
        if self._parent is None:
            raise AttributeNotSetError(f"The _parent attribute of {self!r} has not been set yet.")
        return self._parent

    @property
    def children(self) -> list[TaskNode]:
        """All child nodes of this node."""
        return self._children

    @property
    def children_num(self) -> int:
        """The number of child nodes of this node."""
        return len(self._children)

    @property
    def state(self) -> str:
        """The current state of the node.

        Options:
            "PENDING": Waiting to start execution.
            "ACTIVE": In an active state (currently running).
            "TERMINATED": Has been terminated.
            "EXCEPTION": Encountered an exception.
            "COMPLETED": Completed.
        """
        return self._state

    @property
    def ancestor_chain(self) -> list[TaskNode]:
        """The chain of nodes consisting of all the parent nodes of this node.

        The first is itself, and the last is the top-level node.
        """
        chain = []
        if self.parent == "Null":
            return [self]
        current = self
        while current != "Null":
            chain.append(current)
            current = current.parent
        return chain

    async def terminate_task_node(self):
        """Terminate the task_node.

        This involves detaching the node along with its entire connected subtree from its parent node.
        The parent node will immediately consider this child node as completed,
        but the detached subtree may continue to run,
        potentially leading to side effects. The 'close_task_node' method is safer, but it's not entirely foolproof.
        """
        self._children.clear()
        if self._callback:
            await self.commander._callback_handle(callback=self._callback, which="at_terminate", task_node=self)
        parent = self.parent
        self._state = "TERMINATED"
        if parent != "Null":
            await parent.del_child(self)

    async def close_task_node(self):
        """Terminate the task_node and prevent its descendants from further creating child nodes,
        so as to minimize the side effects of shutting down the node.
        """
        def terminate_children(node: TaskNode, visited=None):
            if visited is None:
                visited = set()
            if node in visited:
                return
            visited.add(node)
            node._state = "TERMINATED"
            for child in node._children:
                terminate_children(child, visited)

        terminate_children(self)
        self._children.clear()

        if self._callback:
            await self.commander._callback_handle(callback=self._callback, which="at_terminate", task_node=self)
        
        parent = self.parent
        if parent != "Null":
            await parent.del_child(self)


T = TypeVar('T')


class CommanderAsyncInterface(TaskNode, Generic[T], metaclass=ABCMeta):
    @property
    @abstractmethod
    def running_status(self) -> bool:
        ...

    @abstractmethod
    def is_empty(self) -> bool:
        ...

    @abstractmethod
    def run(self, job: Job | Sequence[Job] | None = None, auto_exit: bool = False) -> None | T:
        ...

    @abstractmethod
    def run_auto(self, job: Job | Sequence[Job], auto_exit: bool = True) -> bool:
        ...

    @abstractmethod
    def exit(self, return_result: T | None = None) -> None:
        ...

    @abstractmethod
    def wait_for_exit(self) -> None | T:
        ...

    @abstractmethod
    def put_job_threadsafe(self, job: Job) -> None:
        ...

    @abstractmethod
    def call_handler_threadsafe(self, handler: HandlerCoroutine):
        ...


class CommanderAsync(CommanderAsyncInterface[T]):
    _commander_instances = weakref.WeakSet()
    def __init__(self, logger: logging.Logger | None = None):
        super().__init__()
        CommanderAsync._commander_instances.add(self)
        self.__job_queue = asyncio.Queue()
        self._commander = self
        self._children = []
        self._parent = "Null"
        self._callbacks_at_commander_end_list = []
        self._unique_id = itertools.count(1)
        self.__running = False
        self._return_result = None
        self._event_loop: AbstractEventLoop | None = None
        self._running_lock = threading.Lock()
        self.__loop_exit_event = threading.Event()
        self.__loop_exit_event.set()
        self.__thread_exit_event = threading.Event()
        self.__thread_exit_event.set()
        self._id = next(self._unique_id)
        self.logger = logger or get_null_logger()
        self._threadsafe_waiting_tasks = set()
        self._threadsafe_waiting_tasks_lock = threading.Lock()

    @property
    def running_status(self) -> bool:
        with self._running_lock:
            return self.__running
    
    def is_empty(self) -> bool:
        """Check if the commander (task status) is empty.

        Return True only when the __job_queue of the commander, its _children and _threadsafe_waiting_tasks
        are all empty; otherwise, return False.
        """
        with self._threadsafe_waiting_tasks_lock:
            status = self.__job_queue.empty() and not self._children and not self._threadsafe_waiting_tasks
        return status

    def run(self, job: Job | Sequence[Job] | None = None, auto_exit: bool = False, new_queue: bool = True) -> None | T:
        """Start the commander loop.

        It places the job into the loop for execution.
        If auto_exit is set to True, then the loop will automatically exit once the job has finished.

        Args:
            job:
                This job will be added to the __job_queue, waiting to be run by the commander loop.
                It can be a single job or a sequence of jobs.
            auto_exit: If True, the commander loop will automatically eixt after all tasks have been completed.
            new_queue:
                Reset the __job_queue.
                If the commander loop has been previously run and closed,
                there may be residual tasks in the __job_queue.
                This switch allows setting the __job_queue to a new queue when starting the commander loop.

        Raises:
            CommanderAlreadyRunningError: Throw this exception when there is an existing commander loop running.

        Returns:
            None | T:
                When the commander loop ends, return the result specified by the self.exit() method.
                The type of the return value can be specified through generics when instantiating the CommanderAsync.
                If the end is not caused by the exit method, return None.
        """
        with self._running_lock:
            if self.__running is True:
                raise CommanderAlreadyRunningError(f"The commander is already running, commander: {self!r}")
            # The wait here is to ensure that the (potential) commander thread truly terminates.
            # This won't result in a deadlock because if waiting actually occurs here, it indicates that
            # another commander thread is currently terminating and is about to finish, and it won't require
            # the lock before its completion.
            self.__thread_exit_event.wait()
            self.__running = True
            self.__loop_exit_event.clear()
            self.__thread_exit_event.clear()
            if new_queue is True:
                self.__job_queue = asyncio.Queue()
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        try:
            self._event_loop.create_task(self._commander_async(job, auto_exit))
            self._event_loop.run_forever()
        finally:
            for task in asyncio.all_tasks(self._event_loop):
                task.cancel()
            self._event_loop.run_until_complete(self._event_loop.shutdown_asyncgens())
            self._event_loop.close()
            asyncio.set_event_loop(None)
            self._event_loop = None
            self.__thread_exit_event.set()
        return self._return_result

    def run_auto(self, job: Job | Sequence[Job], auto_exit: bool = True, new_queue: bool = True) -> bool:
        """Start the commander loop.

        If there is already a commander loop running,
        it will use that instead of throwing a CommanderAlreadyRunningError,
        and this method returns immediately without blocking.
        If there is no running commander loop,
        it will start one and block the current thread to run this commander loop,
        returning only after the commander loop has finished. 

        Args:
            job:
                This job will be added to the __job_queue, waiting to be run by the commander loop.
                It can be a single job or a sequence of jobs.
            auto_exit: If True, the commander loop will automatically eixt after all tasks have been completed.
            new_queue:
                Reset the __job_queue.
                If the commander loop has been previously run and closed,
                there may be residual tasks in the __job_queue.
                This switch allows setting the __job_queue to a new queue when starting the commander loop.

        Returns:
            bool:
                Return True if a new commander loop is started.
                Return False if using an already existing, running commander loop.
        """
        with self._running_lock:
            if self.__running is True:
                if job is not None:
                    if not isinstance(job, Iterable):
                        job = [job]
                    for one_job in job:
                        self.put_job_threadsafe(one_job)
                return False
            # The wait here is to ensure that the (potential) commander thread truly terminates.
            # This won't result in a deadlock because if waiting actually occurs here, it indicates that
            # another commander thread is currently terminating and is about to finish, and it won't require
            # the lock before its completion.
            self.__thread_exit_event.wait()
            self.__running = True
            self.__loop_exit_event.clear()
            self.__thread_exit_event.clear()
            if new_queue is True:
                self.__job_queue = asyncio.Queue()
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        try:
            self._event_loop.create_task(self._commander_async(job, auto_exit))
            self._event_loop.run_forever()
        finally:
            for task in asyncio.all_tasks(self._event_loop):
                task.cancel()
            self._event_loop.run_until_complete(self._event_loop.shutdown_asyncgens())
            self._event_loop.close()
            asyncio.set_event_loop(None)
            self._event_loop = None
            self.__thread_exit_event.set()
        return True

    def exit(self, return_result: T | None = None, wait: bool = True) -> None:
        """Exit the commander loop.

        Args:
            return_result: This value will be returned by self.run()
            wait: Whether return only after the commander loop and thread has truly finished.
        """
        with self._running_lock:
            self._return_result = return_result
            if self.__running is False:
                return
            #self.__loop_exit_event.clear()
            self.__running = False
            job = ComEnd()
            job._parent = "Null"
            job._commander = self
            self.put_job_threadsafe(job)
            if wait is True:
                self.__loop_exit_event.wait()
                self.__thread_exit_event.wait()

    def wait_for_exit(self) -> None | T:
        """Wait for the commander loop and thread to end.

        This will block the current thread until the commander loop and thread ends,
        and this method returns the value specified by self.exit().        
        """
        # Because this could be a potentially prolonged and blocking wait, using a lock might lead to a deadlock.
        # Thus, we avoid waiting within the lock here.
        # If the following condition is met, it indicates that it is running between
        # self.__running=True and self.__loop_exit_event.clear() in self.run.
        # We wait for these two statements to complete by waiting for the lock (without consuming CPU).
        if self.__running and self.__loop_exit_event.is_set():
            with self._running_lock:
                pass
        self.__loop_exit_event.wait()
        self.__thread_exit_event.wait()
        return self._return_result

    async def _commander_async(self, init_job: Job | Sequence[Job] | None = None, auto_exit: bool = False) -> None:
        """The core of the commander, runs a loop to dispatch tasks.

        In each commander, there is only one running loop to ensure thread safety.
        If coordination between multiple commanders(loops) is required, a thread-safe API can be used.
        
        Args:
            init_job:
                This job will be added to the __job_queue automatically, waiting to be run by the commander loop.
                It can be a single job or a sequence of jobs.
            auto_exit: If True, the commander loop will automatically eixt after all tasks have been completed.

        Raises:
            NotTaskerError: When scheduling a job, if the task of the job is not an actual task object, throw this exception.
        """
        # initial job
        if init_job is not None:
            if not isinstance(init_job, Iterable):
                init_job = [init_job]
            for job in init_job:
                await self._put_job(job=job, parent=self)
        
        while self.__running:
            # stop condition
            if auto_exit:
                await asyncio.sleep(0)
                if self._running_lock.acquire(blocking=False):
                    try:
                        with self._threadsafe_waiting_tasks_lock:
                            if self.__job_queue.empty() and not self._children and not self._threadsafe_waiting_tasks:
                                self.__running = False
                                break
                    finally:
                        self._running_lock.release()
                else:
                    with self._threadsafe_waiting_tasks_lock:
                        if self.__job_queue.empty() and not self._children and not self._threadsafe_waiting_tasks:
                            continue
        
            job = await self.__job_queue.get()

            callback = getattr(job, "callback", None)
            if callback is not None:
                await self._callback_handle(callback=callback, which="at_job_start", task_node=job)
                at_commander_end = callback.at_commander_end
                if at_commander_end:
                    self._callbacks_at_commander_end_list.append(callback)
            
            if job._id is None:
                job._id = next(self._unique_id)
            job_task = job.task
            if getattr(job_task, "_tasker_", None) is not True:
                raise NotTaskerError(f"Task method of {job!r} is not a Tasker.")
            await job_task()

        for callback in self._callbacks_at_commander_end_list:
            await self._callback_handle(callback=callback, which="at_commander_end")
        self._callbacks_at_commander_end_list = []
        # To ensure the order of setting __loop_exit_event and __thread_exit_event.
        # __loop_exit_event.set() must be executed first, followed by _event_loop.stop()
        self.__loop_exit_event.set()
        assert self._event_loop is not None  # For type check
        self._event_loop.stop()

    async def _callback_handle(
        self,
        callback: Callback | None,
        which: CallbackType,
        task_node: TaskNode | None = None,
    ) -> None:
        if callback is None:
            return
        try:
            callbact_list = getattr(callback, which)
        except AttributeError:
            raise ValueError(f"Callback have no '{which}' callback.")
        for callback_job in callbact_list:
            function = callback_job["function"]
            params = callback_job.get("params")
            inject_task_node = callback_job.get("inject_task_node", False)
            if task_node is None:
                task_node = callback._task_node
            if params is None:
                if inject_task_node:
                    if iscoroutinefunction(function):
                        await function(task_node=task_node)
                    else:
                        function(task_node=task_node)
                else:
                    if iscoroutinefunction(function):
                        await function()
                    else:
                        function()
            else:
                args = params.get("args", ())
                kwargs = params.get("kwargs", {})
                if inject_task_node:
                    if iscoroutinefunction(function):
                        await function(*args, **kwargs, task_node=task_node)
                    else:
                        function(*args, **kwargs, task_node=task_node)
                else:
                    if iscoroutinefunction(function):
                        await function(*args, **kwargs)
                    else:
                        function(*args, **kwargs)

    async def _do_at_done(self) -> None:
        job = ComEnd()
        job._parent = "Null"
        job._commander = self
        await self.__job_queue.put(job)

    async def _put_job(self, job: Job, parent: TaskNode | None = None, requester: TaskNode | None = None) -> None:
        if parent is None:
            parent = self
        if requester is None:
            requester = parent
        if parent.state == "TERMINATED":
            return
        parent.add_child(job)
        if job._commander is None:
            job._commander = parent.commander
        
        if not job.commander is self:
            job.commander.put_job_threadsafe(job)
            return
        
        await self.__job_queue.put(job)

    def put_job_threadsafe(self, job: Job) -> None:
        """Add a job to this commander in a thread-safe manner.

        Raises:
            CommanderNotRunError: Throw this error when commander loop is not running.        
        """
        event_loop = self._event_loop
        if event_loop is None:
            raise CommanderNotRunError(f"Commander is not running, commander: {self!r}.")
        future = asyncio.run_coroutine_threadsafe(self._put_job(job), event_loop)
        with self._threadsafe_waiting_tasks_lock:
            self._threadsafe_waiting_tasks.add(future)

        def wrap_discard(obj):
            with self._threadsafe_waiting_tasks_lock:
                self._threadsafe_waiting_tasks.discard(obj)
        future.add_done_callback(wrap_discard)

    def _call_handler(
        self,
        handler: HandlerCoroutine,
        parent: TaskNode | None = None,
        requester: TaskNode | None = None
    ) -> Task | None:
        if getattr(handler, "_handler_", None) is not True:
            raise NotHandlerError(f"{handler!r} is not a Handler, parent: {parent!r}, requester: {requester!r}.")
        
        if parent is None:
            parent = self
        if requester is None:
            requester = parent
        
        if parent.state == "TERMINATED":
            return
        
        parent.add_child(handler)
        if handler._commander is None:
            handler._commander = parent.commander
        if handler._id is None:
            handler._id = next(self._unique_id)
        
        handler_callback = handler.callback
        if handler_callback is not None:
            if handler_callback.at_commander_end:
                handler.commander._callbacks_at_commander_end_list.append(handler_callback)
        
        if handler.commander is not self:
            handler.commander.call_handler_threadsafe(handler)
            return
        
        task = asyncio.create_task(handler.wrap_coroutine())
        return task


    class CallHandlerThreadsafeWrapper:
        def __init__(self, func, *args, **kwargs):
            self.func = func
            self.args = args
            self.kwargs = kwargs

        def execute(self):
            self.func(*self.args, **self.kwargs)


    def _wrap_call_handler(
        self,
        call_handler_threadsafe_wrapper: CallHandlerThreadsafeWrapper
    ) -> Task | None:
        task = call_handler_threadsafe_wrapper.execute()
        with self._threadsafe_waiting_tasks_lock:
            self._threadsafe_waiting_tasks.discard(call_handler_threadsafe_wrapper)
        return task

    def call_handler_threadsafe(self, handler: HandlerCoroutine) -> None:
        """Schedule a handler to be called in this commander in a thread-safe manner.

        Raises:
            CommanderNotRunError: Throw this error when commander loop is not running.        
        """
        event_loop = self._event_loop
        if event_loop is None:
            raise CommanderNotRunError(f"Commander is not running, commander: {self!r}.")
        call_handler_threadsafe_wrapper = self.CallHandlerThreadsafeWrapper(self._call_handler, handler)
        with self._threadsafe_waiting_tasks_lock:
            self._threadsafe_waiting_tasks.add(call_handler_threadsafe_wrapper)
        event_loop.call_soon_threadsafe(self._wrap_call_handler, call_handler_threadsafe_wrapper)

def tasker(password):
    """Decorator for tasker

    Tasks decorated with this decorator should not contain time-consuming tasks that block the thread.
    """
    assert password == PASS_WORD, ("The password is incorrect, "
        "you should ensure that all time-consuming tasks are placed outside of the commander. "
        "Time-consuming tasks pose a risk of blocking the commander. "
        "The correct password is: I assure all time-consuming tasks are delegated externally")
    def decorator(func):
        """Decorate a task in a job.
        
        It Dose:
            If the task return a HandlerCoroutine, call_handler to run it.
            Remove it self from the job when it is done automatically.
        "self_job" refers to the job instance.
        """
        func._tasker_ = True
        @wraps(func)
        async def wrap_function(self_job: Job):
            try:
                if iscoroutinefunction(func):
                    result = await func(self_job)
                else:
                    result = func(self_job)
            except Exception as e:
                self_job._state = "EXCEPTION"
                self_job.commander.logger.error(f"Encountered an exception in the job task. Error: {e}, job: {self_job}")
                await self_job.commander._callback_handle(callback=self_job._callback, which="at_exception", task_node=self_job)
            else:
                if result is not None:
                    assert isinstance(result, HandlerCoroutine)
                    if isinstance(result, HandlerCoroutine):
                        self_job.call_handler(handler=result)
                return result
            finally:
                await self_job.del_child(self_job)

        return wrap_function
    return decorator


class HandlerCoroutine(TaskNode):
    """Handler object

    It can be awaited.

    Attributes:
        coro (Coroutine): The coroutine object wrapped by HandlerCoroutine.
        callback (Callback): Callback of the handler.
    """
    def __init__(self):
        super().__init__()
        self._handler_ = True
        self.coro = None
        self._callback: Callback | None = None

    async def _do_at_done(self):
        """This method is automatically called when the handler is completed.

        It executes the callback functions specified by 'at_handler_end'.
        """
        if self._callback is not None:
            await self.commander._callback_handle(callback=self._callback, which="at_handler_end", task_node=self)
    
    async def wrap_coroutine(self):
        """Wrap the coroutine of handler."""
        # handle "at_handler_start" callback
        if self._callback is not None:
            await self.commander._callback_handle(callback=self._callback, which="at_handler_start", task_node=self)

        assert self.coro is not None
        coro = cast(Coroutine, self.coro)
        try:
            result = await coro
        except Exception as e:
            self._state = "EXCEPTION"
            self.commander.logger.error(f"Encountered an exception in the handler. Error: {e}, handler: {self}")
            await self.commander._callback_handle(callback=self._callback, which="at_exception", task_node=self)
        else:
            return result
        finally:
            await self.del_child(self)

    def __await__(self):
        return self.wrap_coroutine().__await__()

    async def put_job(self, job: Job, parent: TaskNode | None = None, requester: TaskNode | None = None) -> None:
        """Add a job.

        Args:
            job: The job to be added.
            parent: The parent of the job, defaulting to None, indicating the parent is this handler.
            requester:
                The requester of the put_job request,
                defaulting to None, indicating the requester is this handler.
                This parameter may be used when terminating a tasknode.
        """
        commander = self.commander
        await commander._put_job(job=job, parent=parent or self, requester=requester)

    def call_handler(self, handler: HandlerCoroutine, parent: TaskNode | None = None, requester: TaskNode | None = None):
        """Call a handler.

        Args:
            handler: The handler to be called.
            parent: The parent of the job, defaulting to None, indicating the parent is this handler.
            requester:
                The requester of the put_job request,
                defaulting to None, indicating the requester is this handler.
                This parameter may be used when terminating a tasknode.
        """
        commander = self.commander
        commander._call_handler(handler=handler, parent=parent or self, requester=requester)
    
    @property
    def callback(self) -> Callback | None:
        return self._callback

    def add_callback_functions(
        self,
        which: CallbackType,
        functions_info: CallbackDict | list[CallbackDict],
    ) -> None:
        """Add callback functions.

        Args:
            which: Specify the type of the callback functions to be added.
            functions_info: The dict of the callback functions.
        """
        if self._callback is None:
            self._callback = Callback()
        try:
            when_callback = getattr(self._callback, which)
        except AttributeError:
            raise ValueError(
                "The value of 'which' is not one of the supported callback types; "
                "it must represent a type of callback."
            )
        if isinstance(functions_info, list):
            when_callback.extend(functions_info)
        else:
            when_callback.append(functions_info)
        self._callback._task_node = self

    def add_callback(self, callback: Callback | list[Callback | None]) -> None:
        """Add callback."""
        if isinstance(callback, list):
            callback_ = Callback.merge(callback)
        else:
            callback_ = callback
        if self._callback is None:
            self._callback = callback_
        else:
            self._callback.update(callback_)
        self._callback._task_node = self


def _is_first_param_bound(fun) -> bool:
    """Determines if the first parameter of a given function is bound"""
    qualname = fun.__qualname__

    if '.' not in qualname:
        return False

    parts = qualname.split('.')
    
    if parts[-2] == '<locals>':  # Nested function
        return False

    # Is method within class.
    method_name = parts[-1]
    class_name = parts[-2]
    module = sys.modules[fun.__module__]
    cls = getattr(module, class_name, None)
    if cls:
        if isinstance(cls.__dict__.get(method_name), staticmethod):
            return False
        else:
            return True
    else:
        assert False, "The class where the handler is located cannot be a nested local class."

def handler(password):
    """Decorator for handler

    Handlers decorated with this decorator must be a coroutine function,
    and should not contain time-consuming tasks that block the thread.
    The handler can be either a method of a class or a regular function.
    If it is a regular function, it cannot be a nested function,
    as it would then be recognized as a method within a class.
    """
    assert password == PASS_WORD, ("The password is incorrect, "
        "you should ensure that all time-consuming tasks are placed outside of the commander. "
        "Time-consuming tasks pose a risk of blocking the commander. "
        "The correct password is: I assure all time-consuming tasks are delegated externally")
    def decorator(coro_func):
        """
        Decorate a handler to a HandlerCoroutine.
        HandlerCoroutine object dose:
            Automatically add self_handler as the second parameter.
            Remove self from the node's _children, and trigger the down check of this handler task node when it is done.
        """
        if not iscoroutinefunction(coro_func):
            raise TypeError("Handler function must be a coroutine function.")

        @wraps(coro_func)
        def wrap_function(*args, **kwargs):
            handler_coroutine = HandlerCoroutine()
            if _is_first_param_bound(coro_func):
                coro = coro_func(args[0], handler_coroutine, *args[1:], **kwargs)
                for arg in args:
                    if isinstance(arg, Callback):
                        if handler_coroutine._callback is None:
                            handler_coroutine._callback = arg
                        else:
                            handler_coroutine._callback.update(arg)
                        arg._task_node = handler_coroutine
                for value in kwargs.values():
                    if isinstance(value, Callback):
                        if handler_coroutine._callback is None:
                            handler_coroutine._callback = value
                        else:
                            handler_coroutine._callback.update(value)
                        value._task_node = handler_coroutine
            else:
                coro = coro_func(handler_coroutine, *args, **kwargs)
                for arg in args:
                    if isinstance(arg, Callback):
                        if handler_coroutine._callback is None:
                            handler_coroutine._callback = arg
                        else:
                            handler_coroutine._callback.update(arg)
                        arg._task_node = handler_coroutine
                for value in kwargs.values():
                    if isinstance(value, Callback):
                        if handler_coroutine._callback is None:
                            handler_coroutine._callback = value
                        else:
                            handler_coroutine._callback.update(value)
                        value._task_node = handler_coroutine
            handler_coroutine.coro = coro
            return handler_coroutine
       
        return wrap_function
    return decorator


class Params(TypedDict):
    args: tuple
    kwargs: dict


class RequiredCallbackDict(TypedDict):
    function: Callable


class CallbackDict(RequiredCallbackDict, total=False):
    """The dict of functions_info in Callback.

    Keys:
        function (Callable): Required.
        params (Params): NotRequired.
        inject_task_node (bool): NotRequired.
    """
    params: Params
    inject_task_node: bool


class Callback:
    """Callback object.

    It will be automatically executed as a callback by the commander at the appropriate time.
    The supported callback types:
        at_job_start: Executes when the job is going to run.
        at_handler_start: Executes when the handler is going to run.
        at_exception: Executes when an exception occurs.
        at_terminate: Executes when the tasknode is terminated.
        at_handler_end: Executes when the handler is finished.
        at_job_end: Executes when the job is finished.
        at_commander_end: Executes when the commander loop finish.

    Attributes:
        at_job_start (list[CallbackDict]): Dict information of callback functions.
        at_handler_start(list[CallbackDict]): Dict information of callback functions.
        at_exception (list[CallbackDict]): Dict information of callback functions.
        at_terminate (list[CallbackDict]): Dict information of callback functions.
        at_handler_end (list[CallbackDict]): Dict information of callback functions.
        at_job_end (list[CallbackDict]): Dict information of callback functions.
        at_commander_end (list[CallbackDict]): Dict information of callback functions.
        task_node (TaskNode):
            The value of the task_node parameter that is automatically passed back when inject_task_node is True.
    """
    def __init__(
        self,
        at_job_start: list[CallbackDict] | None = None,
        at_handler_start: list[CallbackDict] | None = None,
        at_exception: list[CallbackDict] | None = None,
        at_terminate: list[CallbackDict] | None = None,
        at_handler_end: list[CallbackDict] | None = None,
        at_job_end: list[CallbackDict] | None = None,
        at_commander_end: list[CallbackDict] | None = None,
        task_node: TaskNode | None = None,
        task_node_auto_lock_num: int | None = None,
    ):
        """
        Args:
            at_job_start: [
                # callback when this job is going to run
                {
                    "function": callback_function,
                    "params": {
                        "args": position arguments of callback function
                        "kwargs": key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_handler_start: [
                # callback when this handler is going to run
                {
                    "function": callback_function,
                    "params": {
                        "args": position arguments of callback function
                        "kwargs": key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_exception: [
                # callback when an exception occurs
                {
                    "function": callback_function,
                    "params": {
                        "args": tuple, position arguments of callback function
                        "kwargs": dict, key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_terminate: [
                # callback when the task_node is terminated
                {
                    "function": callback_function,
                    "params": {
                        "args": tuple, position arguments of callback function
                        "kwargs": dict, key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_handler_end: [
                # callback when this handler is finished
                {
                    "function": callback_function,
                    "params": {
                        "args": tuple, position arguments of callback function
                        "kwargs": dict, key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_job_end: [
                # callback when this job is finished
                {
                    "function": callback_function,
                    "params": {
                        "args": tuple, position arguments of callback function
                        "kwargs": dict, key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            at_commander_end: [
                # callback when the commander finish
                {
                    "function": callback_function,
                    "params": {
                        "args": tuple, position arguments of callback function
                        "kwargs": dict, key-values arguments of callback function
                    },
                    "inject_task_node": bool, whether pass back task node into callback function automatically
                },
            ]
            task_node:
                Set the task_node of the callback.
                If not None, the task_node_auto_lock_num will be consumed once during the initialization phase.
                If None, the task_node_auto_lock_num will not be consumed during initialization.
            task_node_auto_lock_num:
                Allow the number of times the _task_node can be set. Once this allowance is exhausted,
                the task_node will be automatically locked and unable to change unless unlocked.
                If set to None, the auto-lock feature will not be enabled.
        """
        self.at_job_start = at_job_start or []
        self.at_handler_start = at_handler_start or []
        self.at_exception = at_exception or []
        self.at_terminate = at_terminate or []
        self.at_handler_end = at_handler_end or []
        self.at_job_end = at_job_end or []
        self.at_commander_end = at_commander_end or []
        self.__task_node_auto_lock_num = task_node_auto_lock_num
        self._task_node_lock = False
        if task_node is None:
            self.__task_node = task_node  # do not consume task_node_auto_lock_num
        else:
            self._task_node = task_node  # consume task_node_auto_lock_num once

    @property
    def task_node(self) -> TaskNode | None:
        return self._task_node

    def task_node_lock(self) -> None:
        self._task_node_lock = True

    def task_node_unlock(self) -> None:
        self._task_node_lock = False

    @property
    def _task_node(self) -> TaskNode | None:
        return self.__task_node

    @_task_node.setter
    def _task_node(self, value: TaskNode) -> None:
        # check whether need to autolock
        if self.__task_node_auto_lock_num is not None:
            if not isinstance(self.__task_node_auto_lock_num, int):
                raise TypeError(f"{self.__task_node_auto_lock_num} is not int, parameter 'task_node_auto_lock_num' passed to Callback have to be int or None.")
            if self.__task_node_auto_lock_num > 0:
                self.__task_node_auto_lock_num -= 1
            else:
                self._task_node_lock = True
        
        if self._task_node_lock is True:
            return
        self.__task_node = value

    def update(self, callbacks: Callback | None | list[Callback | None]) -> Callback:
        fields = ["at_job_start", "at_handler_start", "at_exception", "at_terminate", "at_handler_end", "at_job_end", "at_commander_end"]
        if callbacks is None:
            return self
        elif isinstance(callbacks, Callback):
            callbacks_list = [callbacks]
        else:
            callbacks_list = [callback for callback in callbacks if callback is not None]
        for field in fields:
            for callback in callbacks_list:
                getattr(self, field).extend(getattr(callback, field))
        return self
    
    @classmethod
    def merge(cls, callbacks: list[Callback | None]) -> Callback:
        return Callback().update(callbacks)


class Job(TaskNode, metaclass=ABCMeta):
    """Job object.

    Attributes:
        callback (Callback): Callback of the job.
    """
    def __init__(self, callback: Callback | None = None):
        super().__init__()
        if callback is not None:
            callback._task_node = self
        self._callback = callback

    @abstractmethod
    async def task(self) -> HandlerCoroutine | None:
        """The task of the job.

        Every job must have a specific task assigned.
        This task should not contain time-consuming operations that block the current thread.
        If it returns a handler object, then that handler object will be automatically called,
        with this job as its parent.
        """
        ...

    async def _do_at_done(self):
        """This method is automatically called when the job is completed.

        It executes the callback functions specified by 'at_job_end'.
        """
        if self._callback is not None:
            await self.commander._callback_handle(callback=self._callback, which="at_job_end", task_node=self)

    async def put_job(self, job: Job, parent: TaskNode | None = None, requester: TaskNode | None = None):
        """Add a job.

        Args:
            job: The job to be added.
            parent: The parent of the job, defaulting to None, indicating the parent is this handler.
            requester:
                The requester of the put_job request,
                defaulting to None, indicating the requester is this handler.
                This parameter may be used when terminating a tasknode.
        """
        commander = self.commander
        await commander._put_job(job=job, parent=parent or self, requester=requester)

    def call_handler(self, handler: HandlerCoroutine, parent: TaskNode | None = None, requester: TaskNode | None = None):
        """Call a handler.

        Args:
            handler: The handler to be called.
            parent: The parent of the job, defaulting to None, indicating the parent is this handler.
            requester:
                The requester of the put_job request,
                defaulting to None, indicating the requester is this handler.
                This parameter may be used when terminating a tasknode.
        """
        commander = self.commander
        commander._call_handler(handler=handler, parent=parent or self, requester=requester)

    @property
    def callback(self) -> Callback | None:
        return getattr(self, "_callback", None)

    def add_callback_functions(
        self,
        which: CallbackType,
        functions_info: dict | list[dict],
    ) -> None:
        """Add callback functions.

        Args:
            which: Specify the type of the callback functions to be added.
            functions_info: The dict of the callback functions.
        """
        if self._callback is None:
            self._callback = Callback()
        try:
            when_callback = getattr(self._callback, which)
        except AttributeError:
            raise ValueError(
                "The value of 'which' is not one of the supported callback types; "
                "it must represent a type of callback."
            )
        if isinstance(functions_info, list):
            when_callback.extend(functions_info)
        else:
            when_callback.append(functions_info)
        self._callback._task_node = self

    def add_callback(self, callback: Callback | list[Callback | None]) -> None:
        """Add callback."""
        if isinstance(callback, list):
            callback_ = Callback.merge(callback)
        else:
            callback_ = callback
        if self._callback is None:
            self._callback = callback_
        else:
            self._callback.update(callback_)
        self._callback._task_node = self


class ComEnd(Job):
    """A empty Job with None parent.
    
    Put a empty Job to prevent the commander from waiting indefinitely for a job that will never arrive.
    """
    def __init__(self):
        super().__init__()
    
    @tasker(PASS_WORD)
    async def task(self) -> None:
        pass


class BasicJob(Job):
    """A simple job that calls a handler."""
    def __init__(self, job_content: HandlerCoroutine):
        super().__init__()
        self.job_content = job_content
    
    @tasker(PASS_WORD)
    async def task(self) -> HandlerCoroutine:
        return self.job_content
