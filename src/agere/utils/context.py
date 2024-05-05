"""This module provides management capabilities for context.

Context has the following features:
    1. Save and manage context.
    2. Automatically check and manage context based on the length of the context window.
    3. Bead feature. The bead can always automatically remain within the context window.
        It can be used to provide the most important information or to offer reliable short-term
        memory functionality.
    4. Support tools.

Classes:
    Context: For managing context.
"""


from copy import deepcopy
from typing import Callable, Generic, Literal, TypeVar, TypedDict, overload, cast

from ._tool_base import ToolsManagerInterface, ToolMetadata
from ._exceptions import AgereUtilsError


ContextPiece = TypeVar("ContextPiece")
ContextType = Literal["CUSTOM", "OPENAI"]


class ContextTokenError(AgereUtilsError):
    """Raised when token validation fails."""


class ContextPieceTypeError(AgereUtilsError):
    """Raised when the context piece type is incorrect."""


class BeadLengthInfo(TypedDict):
    START: list[int]
    FLOWING: list[int]
    FIXED: dict[int, list[int]]
    END: list[int]


class BeadContent(TypedDict, Generic[ContextPiece]):
    START: list[ContextPiece]
    FLOWING: list[ContextPiece]
    FIXED: dict[int, list[ContextPiece]]
    END: list[ContextPiece]


class Context(Generic[ContextPiece]):
    """For managing context.

    Attributes:
        token_window (int): The length of context window.
        max_sending_token_num (int): The maximum token number to send.
        context (list): The content of the context.
        bead_content (dict): The contents of the bead, including four types of bead:
            'START', 'FLOWING', 'FIXED' and 'END'.
        bead_lengths (dict): The lenght information of the bead, including three types of bead.
        flowing_bead_position (int): The start index of the flowing bead.
        fixed_bead_positions (list): The list of positions of all fixed bead.
        piece_token_list (list): The list of the token lengths for each piece of the context. 
        token_num (int): The total token number of the context.
        tools_manager(ToolsManager): The tools manager.
    """

    @staticmethod
    def _check_openai_piece(piece: ContextPiece) -> bool:
        """Check if the type of the piece conforms to the OpenAI model specifications."""
        required_keys = {'role', 'content'}
        return isinstance(piece, dict) and required_keys <= piece.keys()

    models_lib = {"OPENAI": _check_openai_piece}
    
    def __init__(
        self,
        model: ContextType = "CUSTOM",
        token_window: int | None = None,
        max_sending_token_num: int | None = None,
        token_counter: Callable[[ContextPiece], int] | None = None,
        token_counter_modifier: Callable[[list[ContextPiece], int], int] | None = None,
        piece_type_validator: Callable[[ContextPiece], bool] | None = None,
        tools_manager: ToolsManagerInterface | None = None,
    ):
        if model not in Context.models_lib and model != "CUSTOM":
            raise NotImplementedError(f"The model of '{model}' is not supported.")
        self._model = model
        self._context: list[ContextPiece] = []
        self._piece_token_list: list[int] = []
        self.token_window: int | None = token_window
        self.max_sending_token_num: int | None = max_sending_token_num
        self._token_counter = token_counter
        self._token_counter_modifier = token_counter_modifier
        self._piece_type_validator = piece_type_validator
        self._bead_content: BeadContent[ContextPiece] = {
            "START": [],
            "FLOWING": [],
            "FIXED": {},
            "END": [],
        }
        self._flowing_bead_position: int = 0  # start index
        self._bead_lengths: BeadLengthInfo = {
            "START": [],
            "FLOWING": [],
            "FIXED": {},
            "END": [],
        }
        self.tools_manager=tools_manager
        self._fixed_bead_position_for_tools: int = -2

    @property
    def context(self) -> list[ContextPiece]:
        return self._context

    @property
    def bead_content(self) -> BeadContent[ContextPiece]:
        return deepcopy(self._bead_content)

    def _bead_content_with_tools(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> BeadContent[ContextPiece]:
        """Get the bead content with the tools taken into consideration."""
        bead_content_copy = deepcopy(self.bead_content)
        bead_content_copy["FIXED"].setdefault(self._fixed_bead_position_for_tools, []).extend(
            self._tools_bead(by_types=by_types, by_names=by_names)
        )
        return bead_content_copy
    
    def _bead_lengths_with_tools(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> BeadLengthInfo:
        """Get the bead content with the tools taken into consideration."""
        bead_lengths_copy = deepcopy(self.bead_lengths)
        bead_lengths_copy["FIXED"].setdefault(self._fixed_bead_position_for_tools, []).extend(
            [
                self.token_counter(piece) for piece in self._tools_bead(
                    by_types=by_types,
                    by_names=by_names,
                )
            ]
        )
        return bead_lengths_copy

    def _tools_bead(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str] | None = None,
    ) -> list[ContextPiece]:
        if self.tools_manager is None or self.tools_manager.tool_model_type != "CUSTOM":
            return []
        tools_metadata_list = self.tools_manager.get_tools_metadata(by_types=by_types, by_names=by_names)
        tools_metadata_list = cast(list[ToolMetadata | Callable], tools_metadata_list)
        return self.tools_manager.wrap_tools_to_bead(tools_metadata_list)

    def token_counter(self, piece: ContextPiece) -> int:
        """Used to calculate the token number of the given context piece."""
        if self._token_counter is None:
            raise NotImplementedError("'token_counter' is not specified.")
        return self._token_counter(piece)

    def token_counter_modifier(self, piece_list: list[ContextPiece], total_token_num: int) -> int:
        """Used to adjust the total token number in a list.

        Args:
            piece_list: A list of context piece to calculate token number for.
            total_token_num: The simple sum of the token number for each piece in the piece list.

        Returns:
            The actual token number corresponding to the piece list.
        """
        if self._token_counter_modifier is None:
            return total_token_num
        return self._token_counter_modifier(piece_list, total_token_num)

    def bead_append(
        self,
        bead: ContextPiece,
        which: Literal["START", "FLOWING", "FIXED", "END"],
        fixed: int | None = None,
    ) -> None:
        """Add bead content.

        Args:
            bead: The bead content to added.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        """
        self.validate_piece_type(bead)
        if which == "FIXED":
            if fixed is None:
                raise ValueError("'fixed' parameter must be specified when which is 'fixed'.")
            self._bead_content["FIXED"].setdefault(fixed, []).append(bead)
            self._bead_lengths["FIXED"].setdefault(fixed, []).append(self.token_counter(bead))
        else:
            self._bead_content[which].append(bead)
            self._bead_lengths[which].append(self.token_counter(bead))

    def bead_extend(
        self,
        beads: list[ContextPiece],
        which: Literal["START", "FLOWING", "FIXED", "END"],
        fixed: int | None = None,
    ) -> None:
        """Add multiple bead contents
        
        Args:
            beads: The list of bead contents to added.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        """
        for bead in beads:
            self.validate_piece_type(bead)
        if which == "FIXED":
            if fixed is None:
                raise ValueError("'fixed' parameter must be specified when which is 'fixed'.")
            self._bead_content["FIXED"].setdefault(fixed, []).extend(beads)
            self._bead_lengths["FIXED"].setdefault(fixed, []).extend(
                self.token_counter(piece) for piece in beads
            )
        else:
            self._bead_content[which].extend(beads)
            self._bead_lengths[which].extend([self.token_counter(piece) for piece in beads])

    def bead_overwrite(
        self,
        new_beads: list[ContextPiece],
        which: Literal["START", "FLOWING", "FIXED", "END"],
        fixed: int | None = None,
    ) -> None:
        """Overwrite the contents of a bead.
        
        Args:
            new_beads: The new bead contents.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        """
        for bead in new_beads:
            self.validate_piece_type(bead)
        if which == "FIXED":
            if fixed is None:
                raise ValueError("'fixed' parameter must be specified when which is 'fixed'.")
            self._bead_content["FIXED"][fixed] = new_beads
            self._bead_lengths["FIXED"][fixed] = [self.token_counter(piece) for piece in new_beads]
        else:
            self._bead_content[which] = new_beads
            self._bead_lengths[which] = [self.token_counter(piece) for piece in new_beads]

    def bead_update(
        self,
        bead: ContextPiece,
        which: Literal["START", "FLOWING", "FIXED", "END"],
        index: int = -1,
        fixed: int | None = None,
    ) -> None:
        """Update the specified piece of the designated bead.
        
        Args:
            bead: The new bead content to update.
            which: Specify the bead type.
            index: Specify the index of the piece to be updated. Default to -1.
            fixed: Specify the fixed bead position.
        """
        self.validate_piece_type(bead)
        if which == "FIXED":
            if fixed is None:
                raise ValueError("'fixed' parameter must be specified when which is 'fixed'.")
            self._bead_content["FIXED"][fixed][index] = bead
            self._bead_lengths["FIXED"][fixed][index] = self.token_counter(bead)
        else:
            self._bead_content[which][index] = bead
            self._bead_lengths[which][index] = self.token_counter(bead)

    @property
    def bead_lengths(self) -> BeadLengthInfo:
        return deepcopy(self._bead_lengths)

    @property
    def flowing_bead_position(self) -> int:
        return self._flowing_bead_position

    @property
    def fixed_bead_positions(self) -> list:
        return list(self.bead_content["FIXED"].keys())

    @property
    def piece_token_list(self) -> list[int]:
        """Give the list of the token lengths for each piece in the context."""
        if len(self._piece_token_list) != len(self._context):
            self._piece_token_list = [self.token_counter(piece) for piece in self._context]
        return self._piece_token_list

    def context_ratio(
        self,
        context: bool = True,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str] | None = None,
        max_sending_token_num: int | Literal["inf"] | None = None,
    ) -> float:
        """Give the ratio of the total length of the specified bead and context to the
        maximum send window length.

        Args:
            context: Whether the completed context content is counted.
            bead: 
                Specify which beads are to be included in the ratio.
                It  can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].
            fixed: Specify the fixed bead position.
            max_sending_token_num:
                Specify the maximum token number to be referenced.
                If there is no limit on the quantity, it ca be set to 'inf'.
                If it is None, use the default max_sending_token_num setting.
                The default value is None.

        Returns:
            float: The ratio of the total lenght of the specified bead and context to the
            maximum send window length.
        """
        if max_sending_token_num is None:
            max_sending_token_num = self.max_sending_token_num
        elif max_sending_token_num == "inf":
            max_sending_token_num = None
        
        if max_sending_token_num is None:
            return 0

        context_included = []
        context_included_lenght_list = []
        bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
        
        tool_names_list = []
        tools_token_num = 0
        if self.tools_manager is not None and self.tools_manager.tool_model_type == "CUSTOM":
            tool_names_list = [tool.name
                for tool in self.tools_manager.get_tools_metadata(
                    by_types=tools_by_types, by_names=tools_by_names,
                )
            ]
        if self.tools_manager is not None and self.tools_manager.tool_model_type != "CUSTOM":
            tools_token_num = self.tools_manager.tools_manual_token_num(
                by_types=tools_by_types,
                by_names=tools_by_names,
            )
        
        if "START" in bead:
            context_included.extend(self.bead_content["START"])
            context_included_lenght_list.extend(self.bead_lengths["START"])

        fixed = [] if "FIXED" not in bead else self.fixed_bead_positions if fixed == "ALL" else fixed
        flowing_backward_index = (
            self.flowing_bead_position - len(self._context)
            if "FLOWING" in bead else None
        )
        mid_content = self._insert_mid_bead(
            piece_list=self._context if context else [],
            fixed=fixed,
            flowing_backward_index=flowing_backward_index,
            tool_names=tool_names_list,
            is_lenght=False,
        )
        mid_content_length_list = self._insert_mid_bead(
            piece_list=self.piece_token_list if context else [],
            fixed=fixed,
            flowing_backward_index=flowing_backward_index,
            tool_names=tool_names_list,
            is_lenght=True,
        )
        context_included.extend(mid_content)
        context_included_lenght_list.extend(mid_content_length_list)
        
        if "END" in bead:
            context_included.extend(self.bead_content["END"])
            context_included_lenght_list.extend(self.bead_lengths["END"])
        length = self._token_num_from_piece_list(
            context_included,
            piece_token_list=context_included_lenght_list
        )
        return (length+tools_token_num) / max_sending_token_num

    @overload
    def _insert_mid_bead(
        self, piece_list: list[ContextPiece],
        fixed: list[int] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str] | None = None,
        is_lenght: bool = False,
    ) -> list[ContextPiece]: ...
    
    @overload
    def _insert_mid_bead(
        self, piece_list: list[int],
        fixed: list[int] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str] | None = None,
        is_lenght: bool = False,
    ) -> list[int]: ...

    def _insert_mid_bead(
        self,
        piece_list: list,
        fixed: list[int] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str] | None = None,
        is_lenght: bool = False,
    ) -> list:
        if flowing_backward_index is not None and flowing_backward_index > -1:
            raise ValueError(
                "'flowing_backward_index' must be negative. "
                f"flowing_backward_index={flowing_backward_index!r}."
            )

        if tool_names and self._should_insert_tools_into_bead():
            bead_content_considering_tools = self._bead_content_with_tools(by_types=[], by_names=tool_names)
            bead_lengths_considering_tools = self._bead_lengths_with_tools(by_types=[], by_names=tool_names)
        else:
            bead_content_considering_tools = self.bead_content
            bead_lengths_considering_tools = self.bead_lengths

        fixed = self.fixed_bead_positions if fixed == "ALL" else fixed
        piece_list_copy = piece_list[:]
        sorted_position = sorted(fixed, key=lambda x: x if x >= 0 else len(piece_list) + x, reverse=True)

        if flowing_backward_index is not None:
            flowing_backward_index = max(flowing_backward_index, -len(piece_list) - 1)
            piece_list_copy[flowing_backward_index:flowing_backward_index] = (
                bead_content_considering_tools["FLOWING"]
                if is_lenght is False
                else bead_lengths_considering_tools["FLOWING"]
            )
            flowing_length = len(bead_content_considering_tools["FLOWING"])
            flowing_forward_index = len(piece_list) + flowing_backward_index + 1
        else:
            flowing_length = 0
            flowing_forward_index = 0

        for position in sorted_position:
            forward_position = position if position >= 0 else len(piece_list) + position + 1
            if forward_position < flowing_forward_index:
                insert_index = max(forward_position, 0)
            elif forward_position == flowing_forward_index:
                insert_index = forward_position if position >=0 else forward_position + flowing_length
            elif forward_position > flowing_forward_index:
                insert_index = min(forward_position + flowing_length, len(piece_list_copy))
            else:
                assert False
            piece_list_copy[insert_index:insert_index] = (
                bead_content_considering_tools["FIXED"][insert_index]
                if is_lenght is False
                else bead_lengths_considering_tools["FIXED"][insert_index]
            )
        return piece_list_copy

    def _should_insert_tools_into_bead(self) -> bool:
        if self.tools_manager is not None and self.tools_manager.tool_model_type== "CUSTOM":
            return True
        else:
            return False

    def context_sending(
        self,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str] | None = None,
        max_sending_token_num: int | Literal["inf"] | None = None,
    ) -> list[ContextPiece]:
        """Give the context content that includes the specified bead, within the range
        of the max_sending_token_num.

        It automatically inserts the contents of the bead and appropriately truncates the context
        to ensure its length stays within the send window.

        Args:
            bead:
                Specify which beads are to be inserted.
                It can be a list consisting of any combination of "START", "FLOWING", "END", and "ALL", 
                with a default value of ["ALL"].
            fixed: Specify the fixed bead position.
            tools_by_types: Specify the tool to be considered by types.
            tools_by_names: Specify the tool to be considered by names.
            max_sending_token_num:
                Specify the maximum token number that can be sent.
                If there is no limit on the quantity, it ca be set to 'inf'.
                If it is None, use the default max_sending_token_num setting.
                The default value is None.

        Returns:
            list: The content of the context with beads within the send window range.
        """
        if max_sending_token_num is None:
            max_sending_token_num = self.max_sending_token_num
        elif max_sending_token_num == "inf":
            max_sending_token_num = None
        if max_sending_token_num is None:
            return self.bead_content["START"] \
                + self._context[:self.flowing_bead_position] \
                + self.bead_content["FLOWING"] \
                + self._context[self.flowing_bead_position:] \
                + self.bead_content["END"]
        
        bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
        fixed = self.fixed_bead_positions if fixed == "ALL" else fixed
        result = []
        used_length = 0
        
        if self._should_insert_tools_into_bead:
            assert self.tools_manager is not None
            tool_names_list = [tool.name
                for tool in self.tools_manager.get_tools_metadata(
                    by_types=tools_by_types, by_names=tools_by_names
                )
            ]
            bead_content_considering_tools = self._bead_content_with_tools(
                by_types=tools_by_types,
                by_names=tools_by_names
            )
            bead_lengths_considering_tools = self._bead_lengths_with_tools(
                by_types=tools_by_types,
                by_names=tools_by_names
            )
        else:
            tool_names_list = []
            bead_content_considering_tools = self.bead_content
            bead_lengths_considering_tools = self.bead_lengths
        
        if self.tools_manager is not None and self.tools_manager.tool_model_type != "CUSTOM":
            max_sending_token_num -= self.tools_manager.tools_manual_token_num(
                by_types=tools_by_types,
                by_names=tools_by_names
            )

        if "START" in bead:
            result.extend(bead_content_considering_tools["START"])
            used_length += sum(bead_lengths_considering_tools["START"])
        if "END" in bead:
            used_length += sum(bead_lengths_considering_tools["END"])
        if "FIXED" in bead:
            used_length += sum(sum(bead_lengths_considering_tools["FIXED"][i]) for i in fixed)
        remaining_length = max_sending_token_num - used_length

        if "FLOWING" in bead:
            mid_content = (
                self._context[:self.flowing_bead_position]
                + bead_content_considering_tools["FLOWING"]
                + self._context[self.flowing_bead_position:]
            )
            trimed_mid_content = self.trim_piece_list_by_token_num(mid_content, remaining_length)
            context_length = len(self._context)
            valid_context_length = len(trimed_mid_content) - len(bead_content_considering_tools["FLOWING"])
            if len(trimed_mid_content) < (
                context_length - self.flowing_bead_position + len(
                    bead_content_considering_tools["FLOWING"]
                )
            ):
                # The flowing bead should be shifted to the end.
                remaining_length -= sum(bead_lengths_considering_tools["FLOWING"])
                trimed_messages = self.trim_piece_list_by_token_num(self._context, remaining_length)
                result.extend(trimed_messages)
                result.extend(bead_content_considering_tools["FLOWING"])
                self._flowing_bead_position = context_length
                valid_context_length = len(trimed_messages)
                flowing_backward_index = -1
            else:
                result.extend(trimed_mid_content)
                flowing_backward_index = context_length - self.flowing_bead_position - 1
        else:
            trimed_mid_content = self.trim_piece_list_by_token_num(self._context, remaining_length)
            result.extend(trimed_mid_content)
            valid_context_length = len(trimed_mid_content) - len(bead_content_considering_tools["FLOWING"])
            flowing_backward_index = None

        if "END" in bead:
            result.extend(bead_content_considering_tools["END"])

        if self._token_counter_modifier is None:
            return result
        else:
            return self._adjust_for_token_modifier(
                valid_context_length=valid_context_length,
                bead=bead,
                fixed=fixed,
                flowing_backward_index=flowing_backward_index,
                tool_names=tool_names_list,
                max_token_num=max_sending_token_num,
                adjust_bead_position=True,
            )
    
    def _adjust_for_token_modifier(
        self,
        valid_context_length: int,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"],
        fixed: list[int] | Literal["ALL"],
        flowing_backward_index: int | None,
        tool_names: list[str],
        max_token_num: int | None = None,
        adjust_bead_position: bool = False,
    ) -> list[ContextPiece]:
        bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
        max_token_num = self.max_sending_token_num if max_token_num is None else max_token_num
        assert max_token_num is not None
        content = []
        content_tokens_list = []

        if valid_context_length <= 0:
            raise ContextTokenError("There is not enough token space.")
        mid_content = self._insert_mid_bead(
            piece_list=self._context[-valid_context_length:] if valid_context_length >= 1 else [],
            fixed=fixed,
            flowing_backward_index=flowing_backward_index,
            tool_names=tool_names,
            is_lenght=False,
        )
        mid_content_tokens_list = self._insert_mid_bead(
            piece_list=self.piece_token_list[-valid_context_length:] if valid_context_length >= 1 else [],
            fixed=fixed,
            flowing_backward_index=flowing_backward_index,
            tool_names=tool_names,
            is_lenght=True
        )

        if "START" in bead:
            content.extend(self.bead_content["START"])
            content_tokens_list.extend(self.bead_lengths["START"])
        content.extend(mid_content)
        content_tokens_list.extend(mid_content_tokens_list)
        if "END" in bead:
            content.extend(self.bead_content["END"])
            content_tokens_list.extend(self.bead_lengths["END"])

        token_num = self._token_num_from_piece_list(
            piece_list=content,
            piece_token_list=content_tokens_list,
        )
        if token_num <= max_token_num:
            return content
        else:
            if (flowing_backward_index is not None and
                valid_context_length < abs(flowing_backward_index)
            ):
                new_flowing_backward_index = -1
                if adjust_bead_position is True:
                    self._flowing_bead_position = len(self._context)
            else:
                new_flowing_backward_index = flowing_backward_index
            return self._adjust_for_token_modifier(
                valid_context_length = valid_context_length - 1,
                bead=bead,
                fixed=fixed,
                flowing_backward_index=new_flowing_backward_index,
                tool_names=tool_names,
                max_token_num=max_token_num,
                adjust_bead_position=adjust_bead_position,
            )
    
    @property
    def token_num(self) -> int:
        return self._token_num_from_piece_list(
            self.context,
            piece_token_list=self.piece_token_list
        )
    
    def _token_num_from_piece_list(
        self,
        piece_list: list[ContextPiece],
        piece_token_list: list[int] | None = None
    ) -> int:
        if self._token_counter is None:
            raise NotImplemented("'token_counter' is not specified.")
        if piece_token_list is not None and len(piece_token_list) == len(piece_list):
            total_token_num = sum(piece_token_list)
        else:
            total_token_num = sum(self.token_counter(piece) for piece in piece_list)
        return self.token_counter_modifier(piece_list, total_token_num)

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
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str] | None = None,
        max_sending_token_num: int | Literal["inf"] | None = None,
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
            fixed: Specify the fixed bead position.
            tools_by_types: Specify the tool to be considered by types.
            tools_by_names: Specify the tool to be considered by names.
            max_sending_token_num:
                Specify the maximum token number that can be sent.
                If there is no limit on the quantity, it ca be set to 'inf'.
                If it is None, use the default max_sending_token_num setting.
                The default value is None.
        
        Returns:
            bool:
                Whether the piece is inserted.
                True: There is enough space for the piece. The piece is inserted.
                False: There is not enough space for the piece. The piece is not inserted.
        """
        if max_sending_token_num is None:
            max_sending_token_num = self.max_sending_token_num
        elif max_sending_token_num == "inf":
            max_sending_token_num = None
        
        self.validate_piece_type(piece)
        if max_sending_token_num is None:
            self._context.append(piece)
            if self._token_counter is not None:
                self._piece_token_list.append(self.token_counter(piece))
            return True
        
        tool_names_list = []
        if self.tools_manager is not None and self.tools_manager.tool_model_type == "CUSTOM":
            tool_names_list = [tool.name
                for tool in self.tools_manager.get_tools_metadata(
                    by_types=tools_by_types, by_names=tools_by_names
                )
            ]
        if self.tools_manager is not None and self.tools_manager.tool_model_type != "CUSTOM":
            max_sending_token_num -= self.tools_manager.tools_manual_token_num(
                by_types=tools_by_types,
                by_names=tools_by_names
            )
        
        minimal_context_token_num = self._get_minimal_context_token_num(
            piece=piece,
            bead=bead,
            fixed=fixed,
            tool_names=tool_names_list,
        )

        if minimal_context_token_num > max_sending_token_num:
            return False
        else:
            self._context.append(piece)
            if self._token_counter is not None:
                self._piece_token_list.append(self.token_counter(piece))
            return True

    def context_extend(
        self,
        piece_list: list[ContextPiece],
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str] | None = None,
        max_sending_token_num: int | Literal["inf"] | None = None,
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
            fixed: Specify the fixed bead position.
            tools_by_types: Specify the tool to be considered by types.
            tools_by_names: Specify the tool to be considered by names.
            max_sending_token_num:
                Specify the maximum token number that can be sent.
                If there is no limit on the quantity, it ca be set to 'inf'.
                If it is None, use the default max_sending_token_num setting.
                The default value is None.
        
        Returns:
            bool:
                Whether the pieces list is inserted.
                True: There is enough space for the pieces list. The pieces list is inserted.
                False: There is not enough space for the pieces list. The pieces list is not inserted.
        """
        if max_sending_token_num is None:
            max_sending_token_num = self.max_sending_token_num
        elif max_sending_token_num == "inf":
            max_sending_token_num = None
        
        for piece in piece_list:
            self.validate_piece_type(piece)
        if max_sending_token_num is None:
            self._context.extend(piece_list)
            if self._token_counter is not None:
                self._piece_token_list.extend(self.token_counter(piece) for piece in piece_list)
            return True
        
        tool_names_list = []
        if self.tools_manager is not None and self.tools_manager.tool_model_type == "CUSTOM":
            tool_names_list = [tool.name
                for tool in self.tools_manager.get_tools_metadata(
                    by_types=tools_by_types, by_names=tools_by_names
                )
            ]
        if self.tools_manager is not None and self.tools_manager.tool_model_type != "CUSTOM":
            max_sending_token_num -= self.tools_manager.tools_manual_token_num(
                by_types=tools_by_types,
                by_names=tools_by_names
            )
        
        minimal_context_token_num = self._get_minimal_context_token_num(
            piece_list=piece_list,
            bead=bead,
            fixed=fixed,
            tool_names=tool_names_list,
        )

        if minimal_context_token_num > max_sending_token_num:
            return False
        else:
            if self._token_counter is not None:
                self._piece_token_list.extend(self.token_counter(piece) for piece in piece_list)
            self._context.extend(piece_list)
            return True

    def _get_minimal_context_token_num(
        self,
        piece: ContextPiece | None = None,
        piece_list: list[ContextPiece] | None = None,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int] | Literal["ALL"] = "ALL",
        tool_names: list[str] | None = None,
    ) -> int:
        if not (piece is None) ^ (piece_list is None):
            raise ValueError("One of 'piece' or 'piece_list' must be specified.")
        bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
        
        if piece is not None:
            pieces = [piece]
        if piece_list is not None:
            pieces = piece_list
        else:
            assert False
        
        minimal_context = []
        minimal_context_token_list = []

        mid_content = self._insert_mid_bead(
            piece_list=pieces,
            fixed=fixed,
            flowing_backward_index = -1 if "FLOWING" in bead else None,
            tool_names=tool_names,
            is_lenght=False,
        )
        mid_content_token_list = self._insert_mid_bead(
            piece_list=[self.token_counter(one_piece) for one_piece in pieces],
            fixed=fixed,
            flowing_backward_index = -1 if "FLOWING" in bead else None,
            tool_names=tool_names,
            is_lenght=True,
        )
        if "START" in bead:
            minimal_context.extend(self.bead_content["START"])
            minimal_context_token_list.extend(self.bead_lengths["START"])
        minimal_context.extend(mid_content)
        minimal_context_token_list.extend(mid_content_token_list)
        if "END" in bead:
            minimal_context.extend(self.bead_content["END"])
            minimal_context_token_list.extend(self.bead_lengths["START"])

        minimal_context_token_num = self._token_num_from_piece_list(
            minimal_context,
            piece_token_list=minimal_context_token_list
        )
        return minimal_context_token_num

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
        self._flowing_bead_position = len(self._context)

    def trim_piece_list_by_token_num(
        self,
        piece_list: list[ContextPiece],
        max_token_num: int,
        modifier: bool = True,
    ) -> list[ContextPiece]:
        """Given a list of context pieces, truncate it according to the max_token_num.

        Args:
            piece_list: The pieces list to be truncated.
            max_token_num: The maximum token number can be included.
            modifer: Whether to consider modifying the token count for the pieces list.

        Returns:
            list: Truncated pieces list.
        """
        if piece_list == self.context:
            position = _find_position(self.piece_token_list, max_token_num)
        else:
            position = _find_position([self.token_counter(piece) for piece in piece_list], max_token_num)
        if modifier is True:
            return self._piece_list_modifier(
                piece_list=piece_list[position:],
                max_token_num=max_token_num,
                piece_token_list=self._piece_token_list
            )
        else:
            return piece_list[position:]

    def _piece_list_modifier(
        self,
        piece_list: list[ContextPiece],
        max_token_num: int,
        piece_token_list: list[int] | None = None
    ) -> list[ContextPiece]:
        if self._token_counter_modifier is None:
            return piece_list
        for i in range(len(piece_list)):
            total_tokens = self._token_num_from_piece_list(
                piece_list=piece_list[i:],
                piece_token_list = piece_token_list[i:] if piece_token_list is not None else None
            )
            if total_tokens <= max_token_num:
                return piece_list[i:]
        raise ContextTokenError("There is not enough token space.")


def _find_position(lst, num):
    """
    Finds the farthest left position in the list where the sum of all elements
    after that position is less than the given number 'num'.
    If you move one position backward, the sum of all elements after that new
    position will be greater than 'num'.
    
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
