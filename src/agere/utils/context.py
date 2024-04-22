"""This module provides management capabilities for context.

Context has the following features:
    1. Save and manage context.
    2. Automatically check and manage context based on the length of the context window.
    3. Bead feature. The bead can always automatically remain within the context window.
    It can be used to provide the most important information or to offer reliable short-term
    memory functionality.

Classes:
    Context: For managing context.
"""


from typing import Callable, Generic, Literal, TypeVar, TypedDict

from ._exceptions import AgereUtilsError


ContextPiece = TypeVar("ContextPiece")
ContextModel = Literal["CUSTOM", "OPENAI"]


class ContextTokensError(AgereUtilsError):
    """Raised when token validation fails."""


class ContextPieceTypeError(AgereUtilsError):
    """Raised when the context piece type is incorrect."""


class BeadInfo(TypedDict):
    start: list[int]
    flowing: list[int]
    end: list[int]


class BeadContent(TypedDict, Generic[ContextPiece]):
    start: list[ContextPiece]
    flowing: list[ContextPiece]
    end: list[ContextPiece]


class Context(Generic[ContextPiece]):
    """For managing context.

    Attributes:
        tokens_window (int): The length of context window.
        max_sending_tokens_num (int): The maximum number of tokens to send.
        context (list): The content of the context.
        bead_content (dict): The contents of the bead, including three types of bead: 'start', 'flowing', and 'end'.
        bead_length (dict): The lenght information of the bead, including three types of bead.
        bead_position (dict): The position information of the bead, including three types of bead.
        bead_info (dict): The information of the bead, including lenght and position.
        piece_token_list (list): The list of the token lengths for each piece of the context. 
        tokens_num (int): The total tokens number of the context.
    """

    @staticmethod
    def _openai_piece_check(piece: ContextPiece) -> bool:
        """Check if the type of the piece conforms to the OpenAI model specifications."""
        required_keys = {'role', 'content'}
        return isinstance(piece, dict) and required_keys <= piece.keys()

    models_lib = {"openai": _openai_piece_check}
    
    def __init__(
        self,
        model: ContextModel = "CUSTOM",
        tokens_window: int | None = None,
        max_sending_tokens_num: int | None = None,
        token_counter: Callable[[ContextPiece], int] | None = None,
        token_counter_modifier: Callable[[list[ContextPiece], int], int] | None = None,
        piece_type_validator: Callable[[ContextPiece], bool] | None = None,
    ):
        if model not in Context.models_lib and model != "CUSTOM":
            raise NotImplementedError(f"The model of '{model}' is not supported.")
        self._model = model
        self._context: list[ContextPiece] = []
        self._piece_token_list: list[int] = []
        self.tokens_window: int | None = tokens_window
        self.max_sending_tokens_num: int | None = max_sending_tokens_num
        self._token_counter = token_counter
        self._token_counter_modifier = token_counter_modifier
        self._piece_type_validator = piece_type_validator
        self._bead_content: BeadContent[ContextPiece] = {"start": [], "flowing": [], "end": []}
        self._bead_position: BeadInfo = {
            "start": [],
            "end": [],
            "flowing": [],
        }  # [start_index, start_index + len(bead)]
        # For example, if a flowing bead with a lenght of 5 is inserted after the tenth element of the context,
        # then self._bead_position = 
        #     {
        #         "start": [0, 0 + len(self._bead_content["start"])],
        #         "flowing": [10, 15],
        #         "end": [len(self._context), len(self._context) + len(self._bead_content["end"])],                     
        #      }
        self._bead_length: BeadInfo = {
            "start": [],
            "end": [],
            "flowing": [],
        }

    @property
    def context(self) -> list[ContextPiece]:
        return self._context

    @property
    def bead_content(self) -> BeadContent[ContextPiece]:
        return self._bead_content

    def token_counter(self, piece: ContextPiece) -> int:
        """Used to calculate the tokens number of the given context piece."""
        if self._token_counter is None:
            raise NotImplementedError("'token_counter' is not specified.")
        return self._token_counter(piece)

    def token_counter_modifier(self, piece_list: list[ContextPiece], total_tokens_num: int) -> int:
        """Used to adjust the total number of tokens in a list.

        Args:
            piece_list: A list of context piece to calculate tokens number for.
            total_tokens_num: The simple sum of the number of tokens for each piece in the piece list.

        Returns:
            The actual number of tokens corresponding to the piece list.
        """
        if self._token_counter_modifier is None:
            return total_tokens_num
        return self._token_counter_modifier(piece_list, total_tokens_num)

    def bead_append(self, bead: ContextPiece, which: Literal["start", "flowing", "end"]) -> None:
        """Add bead content.

        Args:
            bead: The bead content to added.
            which: Specify the bead type.
        """
        self.validate_piece_type(bead)
        self._bead_content[which].append(bead)
        self._bead_length[which].append(self.token_counter(bead))

    def bead_extend(self, beads: list[ContextPiece], which: Literal["start", "flowing", "end"]) -> None:
        """Add multiple bead contents
        
        Args:
            beads: The list of bead contents to added.
            which: Specify the bead type.
        """
        for bead in beads:
            self.validate_piece_type(bead)
        self._bead_content[which].extend(beads)
        self._bead_length[which].extend([self.token_counter(piece) for piece in beads])

    def bead_update(self, new_beads: list[ContextPiece], which: Literal["start", "flowing", "end"]) -> None:
        """Rewrite the contents of a bead.
        
        Args:
            new_beads: The new bead contents.
            which: Specify the bead type.
        """
        for bead in new_beads:
            self.validate_piece_type(bead)
        self._bead_content[which] = new_beads
        self._bead_length[which] = [self.token_counter(piece) for piece in new_beads]

    @property
    def bead_length(self) -> BeadInfo:
        return self._bead_length

    @property
    def bead_position(self) -> BeadInfo:
        return self._bead_position

    @property
    def bead_info(self) -> dict[str, BeadInfo]:
        return {"position": self.bead_position, "length": self.bead_length}

    @property
    def piece_token_list(self) -> list[int]:
        """Give the list of the token lengths for each piece in the context."""
        if len(self._piece_token_list) != len(self._context):
            self._piece_token_list = [self.token_counter(piece) for piece in self._context]
        return self._piece_token_list

    def bead_ratio(self, bead: list[Literal["START", "FLOWING", "END", "ALL"]] | None = None) -> float:
        """Give the ratio of the total length of the specified bead to the maximum send window length.

        Args:
            bead: 
                Specify which beads are to be included in the ratio.
                It  can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].

        Returns:
            float: The ratio of the total lenght of the specified bead to the maximum send window length.
        """
        if self.max_sending_tokens_num is None:
            return 0
        bead = bead or ["ALL"]
        if "ALL" in bead:
            bead = ["START", "FLOWING", "END"]
        bead_length = 0
        assert bead is not None
        if "START" in bead:
            bead_length += sum(self.bead_length["start"])
        if "FLOWING" in bead:
            bead_length += sum(self.bead_length["flowing"])
        if "END" in bead:
            bead_length += sum(self.bead_length["end"])
        return bead_length / self.max_sending_tokens_num

    def context_sending(
        self,
        bead: list[Literal["START", "FLOWING", "END", "ALL"]] | None = None,
    ) -> list[ContextPiece]:
        """Give the context content that includes the specified bead, within the range of the max_sending_tokens_num.

        It automatically inserts the contents of the bead and appropriately truncates the context
        to ensure its length stays within the send window.

        Args:
            bead:
                Specify which beads are to be inserted.
                It can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].

        Returns:
            list: The content of the context with beads within the send window range.
        """
        if self.max_sending_tokens_num is None:
            return self.bead_content["start"] \
                + self._context[: self.bead_position["flowing"][0]] \
                + self.bead_content["flowing"] \
                + self._context[self.bead_position["flowing"][0] :] \
                + self.bead_content["end"]
        bead = ["ALL"] if bead is None else bead
        if "ALL" in bead:
            bead = ["START", "FLOWING", "END"]
        result = []
        used_length = 0
        assert bead is not None
        if "START" in bead:
            result.extend(self.bead_content["start"])
            used_length += sum(self.bead_length["start"])
        if "END" in bead:
            used_length += sum(self.bead_length["end"])
        remaining_length = self.max_sending_tokens_num - used_length
        if "FLOWING" in bead:
            mid_content = (
                self._context[: self.bead_position["flowing"][0]]
                + self.bead_content["flowing"]
                + self._context[self.bead_position["flowing"][0] :]
            )
            trimed_mid_content = self.trim_piece_list_by_tokens(mid_content, remaining_length)
            context_length = len(self._context)
            if len(trimed_mid_content) < (
                context_length - self.bead_position["flowing"][0]
                + len(self.bead_content["flowing"])
            ):
                # The flowing bead should be shifted to the end.
                remaining_length -= sum(self.bead_length["flowing"])
                trimed_messages = self.trim_piece_list_by_tokens(self._context, remaining_length)
                assert trimed_messages
                result.extend(trimed_messages)
                result.extend(self.bead_content["flowing"])
                self.bead_position["flowing"] = [
                        context_length,
                        context_length + len(self.bead_content["flowing"])
                ]
            else:
                result.extend(trimed_mid_content)
        else:
            result.extend(self.trim_piece_list_by_tokens(self._context, remaining_length))

        if "END" in bead:
            result.extend(self.bead_content["end"])

        if self._token_counter_modifier is None:
            return result
        else:
            return self._adjust_for_token_modifier(
                piece_list_length=len(result),
                bead=bead,
                max_tokens_num=self.max_sending_tokens_num,
                adjust_bead_position=True,
            )
    
    def _adjust_for_token_modifier(
        self,
        piece_list_length: int,
        bead: list[Literal["START", "FLOWING", "END", "ALL"]],
        max_tokens_num: int,
        adjust_bead_position: bool = False,
    ) -> list[ContextPiece]:
        if "FLOWING" not in bead:
            mid_content_length = piece_list_length - len(self.bead_content["start"]) - len(self.bead_content["end"])
            if mid_content_length <= 0:
                raise ValueError("'piece_list_length' is less than total bead lenght.")
            mid_content_start_index = len(self._context) - mid_content_length
            for i in range(mid_content_length):
                piece_list_result = self.bead_content["start"] \
                    + self._context[mid_content_start_index + i :] \
                    + self.bead_content["end"]
                total_tokens = self._tokens_num_from_piece_list(
                    piece_list = piece_list_result, 
                    piece_token_list = self.bead_length["start"]
                        + self.piece_token_list[mid_content_start_index + i :]
                        + self.bead_length["end"]
                )
                if total_tokens <= max_tokens_num:
                    return piece_list_result
            raise ContextTokensError("There is not enough token space left for messages.")

        mid_content_length = piece_list_length - len(self.bead_content["start"]) - len(self.bead_content["end"])\
            - len(self.bead_content["flowing"])
        if mid_content_length <= 0:
            raise ValueError("'piece_list_length' is less than total bead lenght.")
        before_flowing_start_index = len(self._context) - mid_content_length
        before_flowing_end_index = self.bead_position["flowing"][0]
        after_flowing_start_index = max(before_flowing_end_index, before_flowing_start_index)
        after_flowing_end_index = len(self._context)
        for i in range(before_flowing_end_index - before_flowing_start_index):
            piece_list_result = self.bead_content["start"] \
                + self._context[before_flowing_start_index + i : before_flowing_end_index] \
                + self.bead_content["flowing"] \
                + self._context[after_flowing_start_index : after_flowing_end_index] \
                + self.bead_content["end"]
            total_tokens = self._tokens_num_from_piece_list(
                piece_list = piece_list_result, 
                piece_token_list = self.bead_length["start"]
                    + self.piece_token_list[before_flowing_start_index + i : before_flowing_end_index]
                    + self.bead_length["flowing"]
                    + self.piece_token_list[after_flowing_start_index : after_flowing_end_index]
                    + self.bead_length["end"]
            )
            if total_tokens <= max_tokens_num:
                return piece_list_result
        for i in range(after_flowing_end_index - after_flowing_start_index):
            piece_list_result = self.bead_content["start"] \
                + self._context[after_flowing_start_index + i : after_flowing_end_index] \
                + self.bead_content["flowing"] \
                + self.bead_content["end"]
            total_tokens = self._tokens_num_from_piece_list(
                piece_list = piece_list_result,
                piece_token_list = self.bead_length["start"]
                    + self.piece_token_list[after_flowing_start_index + i : after_flowing_end_index]
                    + self.bead_length["flowing"]
                    + self.bead_length["end"]
            )
            if total_tokens <= max_tokens_num:
                if adjust_bead_position is True:
                    self.bead_position["flowing"] = [
                            len(self._context),
                            len(self._context) + len(self.bead_content["flowing"])
                    ]
                return piece_list_result
        raise ContextTokensError("There is not enough token space left for messages.")
    
    @property
    def tokens_num(self) -> int:
        return self._tokens_num_from_piece_list(self.context, piece_token_list=self.piece_token_list)
    
    def _tokens_num_from_piece_list(self, piece_list: list[ContextPiece], piece_token_list: list[int] | None = None) -> int:
        if self._token_counter is None:
            raise NotImplemented("'token_counter' is not specified.")
        if piece_token_list is not None:
            total_tokens_num = sum(piece_token_list)
        else:
            total_tokens_num = sum(self.token_counter(piece) for piece in piece_list)
        return self.token_counter_modifier(piece_list, total_tokens_num)

    def validate_piece_type(self, piece: ContextPiece) -> bool:
        """Check if the type of the context piece is correct."""
        if self._model == "CUSTOM":
            if self._piece_type_validator is None:
                result = True
            else:
                result = self._piece_type_validator(piece)
        else:
            if self._model not in Context.models_lib:
                raise ValueError(f"The model of '{self._model!r}' is not supported.")
            result = Context.models_lib[self._model](piece)
        if not result:
            raise ContextPieceTypeError(f"The type of the context piece is incorrect. Piece: {piece!r}")
        return result

    def context_append(
        self,
        piece: ContextPiece,
        bead: list[Literal["ALL", "START", "END", "FLOWING"]] | None = None
    ) -> bool:
        """Add context content.

        It will automatically verify if there is enough space to insert the context piece
        when all the specified beads contents are included.
        If there is sufficient space, it will insert the piece and return True;
        otherwise, it will not insert the piece and return False.
        This ensures that the piece inserted is valid and can be sent.

        Args:
            piece: The context piece to be added.
            bead:
                Specify the beads to be checked with.
                It can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].
        
        Returns:
            bool:
                Whether the piece is inserted.
                True: There is enough space for the piece. The piece is inserted.
                False: There is not enough space for the piece. The piece is not inserted.
        """
        self.validate_piece_type(piece)
        if self.max_sending_tokens_num is None:
            self._context.append(piece)
            if self._token_counter is not None:
                self._piece_token_list.append(self.token_counter(piece))
            return True

        minimal_context_tokens_num = self._get_minimal_context_tokens_num(piece=piece, bead=bead)

        if minimal_context_tokens_num > self.max_sending_tokens_num:
            return False
        else:
            self._context.append(piece)
            if self._token_counter is not None:
                self._piece_token_list.append(self.token_counter(piece))
            return True

    def context_extend(
        self,
        piece_list: list[ContextPiece],
        bead: list[Literal["ALL", "START", "END", "FLOWING"]] | None = None
    ) -> bool:
        """Add multiple context contents.

        It will automatically verify if there is enough space to insert the context pieces list
        when all the specified beads contents are included.
        If there is sufficient space, it will insert the pieces list and return True;
        otherwise, it will not insert the pieces list and return False.
        This ensures that the pieces list inserted is valid and can be sent.

        Args:
            piece_list: The context piece to be added.
            bead:
                Specify the beads to be checked with.
                It can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].
        
        Returns:
            bool:
                Whether the pieces list is inserted.
                True: There is enough space for the pieces list. The pieces list is inserted.
                False: There is not enough space for the pieces list. The pieces list is not inserted.
        """
        for piece in piece_list:
            self.validate_piece_type(piece)
        if self.max_sending_tokens_num is None:
            self._context.extend(piece_list)
            if self._token_counter is not None:
                self._piece_token_list.extend(self.token_counter(piece) for piece in piece_list)
            return True
        
        minimal_context_tokens_num = self._get_minimal_context_tokens_num(piece_list=piece_list, bead=bead)

        if minimal_context_tokens_num > self.max_sending_tokens_num:
            return False
        else:
            if self._token_counter is not None:
                self._piece_token_list.extend(self.token_counter(piece) for piece in piece_list)
            self._context.extend(piece_list)
            return True

    def _get_minimal_context_tokens_num(
        self,
        piece: ContextPiece | None = None,
        piece_list: list[ContextPiece] | None = None,
        bead: list[Literal["ALL", "START", "FLOWING", "END"]] | None = None,
    ) -> int:
        if not (piece is None) ^ (piece_list is None):
            raise ValueError
        bead = bead or ["ALL"]
        if "ALL" in bead:
            bead = ["START", "FLOWING", "END"]
        minimal_context = []
        assert bead is not None
        if "START" in bead:
            minimal_context.extend(self.bead_content["start"])
        if piece is not None:
            minimal_context.append(piece)
        if piece_list is not None:
            minimal_context.extend(piece_list)
        if "FLOWING" in bead:
            minimal_context.extend(self.bead_content["flowing"])
        if "END" in bead:
            minimal_context.extend(self.bead_content["end"])
        minimal_context_tokens_num = self._tokens_num_from_piece_list(minimal_context)
        return minimal_context_tokens_num

    def context_update(self, context: list[ContextPiece]) -> None:
        """Update (rewrite) the content of context."""
        for piece in context:
            self.validate_piece_type(piece)
        self._context = context
        if self._token_counter is not None:
            self._piece_token_list = [self.token_counter(piece) for piece in context]
        else:
            self._piece_token_list = []

    def shift_flowing_bead(self) -> None:
        """Move the flowing bead to the end of the context."""
        self._bead_position["flowing"] = [len(self._context), len(self._context) + len(self._bead_content["flowing"])]

    def trim_piece_list_by_tokens(
        self,
        piece_list: list[ContextPiece],
        max_tokens_num: int,
        modifier: bool = True,
    ) -> list[ContextPiece]:
        """Given a list of context pieces, truncate it according to the max_tokens_num.

        Args:
            piece_list: The pieces list to be truncated.
            max_tokens_num: The maximum number of tokens can be included.
            modifer: Whether to consider modifying the token count for the pieces list.

        Returns:
            list: Truncated pieces list.
        """
        if piece_list == self.context:
            position = _find_position(self.piece_token_list, max_tokens_num)
        else:
            position = _find_position([self.token_counter(piece) for piece in piece_list], max_tokens_num)
        if modifier is True:
            return self._piece_list_modifier(
                piece_list=piece_list[position:],
                max_tokens_num=max_tokens_num,
                piece_token_list=self._piece_token_list
            )
        else:
            return piece_list[position:]

    def _piece_list_modifier(
        self,
        piece_list: list[ContextPiece],
        max_tokens_num: int,
        piece_token_list: list[int] | None = None
    ) -> list[ContextPiece]:
        if self._token_counter_modifier is None:
            return piece_list
        for i in range(len(piece_list)):
            total_tokens = self._tokens_num_from_piece_list(
                piece_list=piece_list[i:],
                piece_token_list = piece_token_list[i:] if piece_token_list is not None else None
            )
            if total_tokens <= max_tokens_num:
                return piece_list[i:]
        raise ContextTokensError("There is not enough token space.")


def _find_position(lst, num):
    """
    Finds the farthest left position in the list where the sum of all elements after that position is less than the given number 'num'.
    If you move one position backward, the sum of all elements after that new position will be greater than 'num'.
    
    Args:
        - lst {list}: The list of integers.
        - num {int}: The target number.
    
    Returns:
        int: The 1-based index of the position found, (index + 1)
        return 0 if the sum of all integers is less than num,
        return the length of lst if the last integers is greater than num.
    """
    prefix_sum = [0]
    for x in lst:
        prefix_sum.append(prefix_sum[-1] + x)

    left, right = 0, len(prefix_sum) - 1

    while left < right:
        mid = (left + right) // 2
        if prefix_sum[-1] - prefix_sum[mid] < num:
            right = mid
        else:
            left = mid + 1

    return left
