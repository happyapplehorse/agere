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
from typing import Callable, Generic, Literal, TypedDict, overload, cast

from ._context_model_base import ContextModelBase, ContextPiece
from ._tool_base import ToolsManagerInterface, ToolMetadata, ToolKit
from ._exceptions import AgereUtilsError


class ContextTokenError(AgereUtilsError):
    """Raised when token validation fails."""


class ContextPieceTypeError(AgereUtilsError):
    """Raised when the context piece type is incorrect."""


class BeadLengthInfo(TypedDict):
    START: list[int]
    FLOWING: list[int]
    FIXED: dict[int | str, list[int]]
    END: list[int]


class BeadContent(TypedDict, Generic[ContextPiece]):
    START: list[ContextPiece]
    FLOWING: list[ContextPiece]
    FIXED: dict[int | str, list[ContextPiece]]
    END: list[ContextPiece]


class Context(Generic[ContextPiece]):
    """For managing context.

    Attributes:
        context_model (ContextModelBase): The context model.
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
        tools_manager (ToolsManager): The tools manager.
        fixed_bead_position_for_tools (int | str): The fixed bead position for tools.
    """


    def __init__(
        self,
        context_model: ContextModelBase[ContextPiece],
        token_window: int | None = None,
        max_sending_token_num: int | None = None,
        tools_manager: ToolsManagerInterface | None = None,
    ):
        """Init a Context object.
        
        A context piece refers to a fundamental unit that constitutes the entire context,
        and a list composed of several context pieces forms a complete context.

        Args:
            model:
                Specify the name of the context model type. For custom types, select "CUSTOM";
                for other types, use the name of the context model, such as "OPENAI".
            token_window: Specify the valid context window size for the LLM.
            max_sending_token_num:
                Specify the maximum nuber of tokens to be sent.
                For example, if the context window size is 8K tokens, you might want to set the maximum
                sent token count to 5K, leaving the remaining 3K space for the LLM to generate its output.
            tools_manager:
                Specify the tool manager.
        """
        self.context_model = context_model
        self._context: list[ContextPiece] = []
        self._piece_token_list: list[int] = []
        self.token_window: int | None = token_window
        self.max_sending_token_num: int | None = max_sending_token_num
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
        self.fixed_bead_position_for_tools: int | str = -2

    @property
    def context(self) -> list[ContextPiece]:
        return self._context

    @property
    def bead_content(self) -> BeadContent[ContextPiece]:
        return deepcopy(self._bead_content)

    def _bead_content_with_tools(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> BeadContent[ContextPiece]:
        """Get the bead content with the tools taken into consideration."""
        bead_content_copy = deepcopy(self.bead_content)
        bead_content_copy["FIXED"].setdefault(self.fixed_bead_position_for_tools, []).extend(
            self._tools_bead(by_types=by_types, by_names=by_names)
        )
        return bead_content_copy
    
    def _bead_lengths_with_tools(
        self,
        by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        by_names: list[str | ToolKit] | None = None,
    ) -> BeadLengthInfo:
        """Get the bead content with the tools taken into consideration."""
        bead_lengths_copy = deepcopy(self.bead_lengths)
        bead_lengths_copy["FIXED"].setdefault(self.fixed_bead_position_for_tools, []).extend(
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
        by_names: list[str | ToolKit] | None = None,
    ) -> list[ContextPiece]:
        if self.tools_manager is None or self.tools_manager.tool_model_type != "CUSTOM":
            return []
        tools_metadata_list = self.tools_manager.get_tools_metadata(by_types=by_types, by_names=by_names)
        tools_metadata_list = cast(list[ToolMetadata | Callable], tools_metadata_list)
        return self.tools_manager.wrap_tools_to_bead(tools_metadata_list)

    def token_counter(self, piece: ContextPiece) -> int:
        """Used to calculate the token number of the given context piece."""
        return self.context_model.token_counter(piece)

    def token_counter_modifier(self, piece_list: list[ContextPiece], total_token_num: int) -> int:
        """Used to adjust the total token number in a list.

        Args:
            piece_list: A list of context piece to calculate token number for.
            total_token_num: The simple sum of the token number for each piece in the piece list.

        Returns:
            The actual token number corresponding to the piece list.
        """
        return self.context_model.token_counter_modifier(piece_list, total_token_num)

    def bead_append(
        self,
        bead: ContextPiece,
        which: Literal["START", "FLOWING", "FIXED", "END"],
        fixed: int | str | None = None,
    ) -> None:
        """Add bead content.

        Args:
            bead: The bead content to added.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        
        Raises:
            ValueError: When which is 'FIXED' but fixed not specified.
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
        fixed: int | str | None = None,
    ) -> None:
        """Add multiple bead contents
        
        Args:
            beads: The list of bead contents to added.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        
        Raises:
            ValueError: When which is 'FIXED' but fixed not specified.
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

    def bead_update(
        self,
        new_beads: list[ContextPiece],
        which: Literal["START", "FLOWING", "FIXED", "END"],
        fixed: int | str | None = None,
    ) -> None:
        """Update the contents of a bead.
        
        Args:
            new_beads: The new bead contents.
            which: Specify the bead type.
            fixed: Specify the fixed bead position.
        
        Raises:
            ValueError: When which is 'FIXED' but fixed not specified.
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

    def bead_piece_overwrite(
        self,
        bead: ContextPiece,
        which: Literal["START", "FLOWING", "FIXED", "END"],
        index: int = -1,
        fixed: int | str | None = None,
    ) -> None:
        """Overwrite the specified piece of the designated bead.
        
        Args:
            bead: The new bead content to overwrite.
            which: Specify the bead type.
            index: Specify the index of the piece to be overwriten. Default to -1.
            fixed: Specify the fixed bead position.

        Raises:
            ValueError: When which is 'FIXED' but fixed not specified.
            KeyError: When the 'fixed' key dose not exist within the FIXED bead dict.
            IndexError: When the 'index' is invalid.
        """
        self.validate_piece_type(bead)
        if which == "FIXED":
            if fixed is None:
                raise ValueError("'fixed' parameter must be specified when which is 'fixed'.")
            try:
                self._bead_content["FIXED"][fixed][index] = bead
                self._bead_lengths["FIXED"][fixed][index] = self.token_counter(bead)
            except KeyError as e:
                raise KeyError(f"The key '{fixed}' dose not exist in the 'FIXED' bead dict.") from e
            except IndexError as e:
                raise IndexError(f"The index '{index}' is not a valid index for the fixed bead of '{fixed}'.") from e
        else:
            try:
                self._bead_content[which][index] = bead
                self._bead_lengths[which][index] = self.token_counter(bead)
            except IndexError as e:
                raise IndexError(f"The index '{index}' is not a valid index for the '{which}' type of bead.") from e

    def bead_piece_delete(
        self,
        which: Literal["START", "FLOWING", "FIXED", "END"],
        index: int,
        fixed: int | str | None = None,
    ) -> None:
        """Remove the specified piece of the designated bead.
        
        Args:
            which: Specify the bead type.
            index: Specify the index of the piece to be removed.
            fixed: Specify the fixed bead position.
        
        Raises:
            ValueError: When which is 'FIXED' but fixed not specified.
            KeyError: When the 'fixed' key dose not exist within the FIXED bead dict.
            IndexError: When the 'index' is invalid.
        """
        if which == "FIXED":
            try:
                if fixed is None:
                    raise ValueError("The 'fixed' can not be None when which equals to 'FIXED'.")
                del self._bead_content["FIXED"][fixed][index]
                del self._bead_lengths["FIXED"][fixed][index]
            except KeyError as e:
                raise KeyError(f"The key '{fixed}' dose not exist in the 'FIXED' bead dict.") from e
            except IndexError as e:
                raise IndexError(f"The index '{index}' is not a valid index for the fixed bead of '{fixed}'.") from e
        else:
            try:
                del self._bead_content[which][index]
                del self._bead_lengths[which][index]
            except IndexError as e:
                raise IndexError(f"The index '{index}' is not a valid index for the bead of '{which}'.") from e

    @property
    def bead_lengths(self) -> BeadLengthInfo:
        return deepcopy(self._bead_lengths)

    @property
    def flowing_bead_position(self) -> int:
        """The current position of the flowing bead.

        Note: This value may change when obtaining the context_sending.
        """
        assert self._flowing_bead_position >= 0
        if self._flowing_bead_position >= 0:
            return self._flowing_bead_position
        elif self._flowing_bead_position >= -len(self._context):
            return self._flowing_bead_position + len(self._context)
        else:
            assert False

    @property
    def fixed_bead_positions(self) -> list:
        return list(self.bead_content["FIXED"].keys())

    @property
    def piece_token_list(self) -> list[int]:
        """Give the list of the token lengths for each piece in the context."""
        if len(self._piece_token_list) != len(self._context):
            self._piece_token_list = [self.token_counter(piece) for piece in self._context]
        return self._piece_token_list

    def _get_fixed_bead_config_with_tool(
        self,
        fixed: list[int | str] | Literal["ALL"],
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"],
    ) -> tuple[list[int | str], list[Literal["START", "FLOWING", "FIXED", "END"]]]:
        if fixed == "ALL":
            new_fixed = self.fixed_bead_positions
        else:
            new_fixed = fixed[:]
        if self.fixed_bead_position_for_tools not in new_fixed and self._should_insert_tools_into_bead:
            new_fixed.append(self.fixed_bead_position_for_tools)
        
        if bead == "ALL":
            new_bead = ["START", "FLOWING", "FIXED", "END"]
        else:
            new_bead = bead[:]
        if "FIXED" not in new_bead and self._should_insert_tools_into_bead:
            new_bead.append("FIXED")

        new_bead = cast(list[Literal["START", "FLOWING", "FIXED", "END"]], new_bead)
        return new_fixed, new_bead

    def context_ratio(
        self,
        context: bool = True,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str | ToolKit] | None = None,
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
            tools_by_types: Specify the tools by types. Default to "ALL".
            tools_by_names: Specify the tools by names. Default to None.
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
        if tools_by_types or tools_by_names:
            fixed, bead = self._get_fixed_bead_config_with_tool(fixed=fixed, bead=bead)
        
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
            self.flowing_bead_position - len(self._context) - 1
            if "FLOWING" in bead else None
        )
        tool_names_list = cast(list[str | ToolKit], tool_names_list)
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
        self,
        piece_list: list[ContextPiece],
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str | ToolKit] | None = None,
        is_lenght: bool = False,
    ) -> list[ContextPiece]: ...
    
    @overload
    def _insert_mid_bead(
        self,
        piece_list: list[int],
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str | ToolKit] | None = None,
        is_lenght: bool = False,
    ) -> list[int]: ...

    def _insert_mid_bead(
        self,
        piece_list: list,
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        flowing_backward_index: int | None = None,
        tool_names: list[str | ToolKit] | None = None,
        is_lenght: bool = False,
    ) -> list:
        if flowing_backward_index is not None and flowing_backward_index > -1:
            raise ValueError(
                "'flowing_backward_index' must be negative. "
                f"flowing_backward_index={flowing_backward_index!r}."
            )

        if tool_names and self._should_insert_tools_into_bead:
            bead_content_considering_tools = self._bead_content_with_tools(by_types=[], by_names=tool_names)
            bead_lengths_considering_tools = self._bead_lengths_with_tools(by_types=[], by_names=tool_names)
        else:
            bead_content_considering_tools = self.bead_content
            bead_lengths_considering_tools = self.bead_lengths

        fixed = self.fixed_bead_positions if fixed == "ALL" else fixed

        dynamic_fixed_info = [
            {
                "key": position,
                "dynamic_position": self._get_dynamic_position(
                    position=position,
                    length = (
                        len(piece_list) + len(bead_content_considering_tools["FLOWING"])
                        if flowing_backward_index is not None
                        else len(piece_list)
                    ),
                ),
            } for position in fixed
        ]

        piece_list_copy = piece_list[:]
        # Sort by actual position from back to front.
        sorted_fixed_info = sorted(
            dynamic_fixed_info,
            key=lambda x: (
                x["dynamic_position"]
                if x["dynamic_position"] >= 0
                else len(piece_list) + x["dynamic_position"]
            ),
            reverse=True,
        )

        # Insert flowing beads.
        if flowing_backward_index is not None:
            flowing_backward_index = max(flowing_backward_index, -len(piece_list) - 1)
            flowing_forward_index = len(piece_list) + flowing_backward_index + 1
            piece_list_copy[flowing_forward_index:flowing_forward_index] = (
                bead_content_considering_tools["FLOWING"]
                if is_lenght is False
                else bead_lengths_considering_tools["FLOWING"]
            )

        # Insert fixed beads.
        for info in sorted_fixed_info:
            forward_position = (
                info["dynamic_position"]
                if info["dynamic_position"] >= 0
                else len(piece_list_copy) + info["dynamic_position"] + 1
            )
            forward_position = min(max(forward_position, 0), len(piece_list_copy))

            piece_list_copy[forward_position:forward_position] = (
                bead_content_considering_tools["FIXED"][info["key"]]
                if is_lenght is False
                else bead_lengths_considering_tools["FIXED"][info["key"]]
            )
        return piece_list_copy

    @property
    def _should_insert_tools_into_bead(self) -> bool:
        if self.tools_manager is not None and self.tools_manager.tool_model_type == "CUSTOM":
            return True
        else:
            return False

    def context_sending(
        self,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str | ToolKit] | None = None,
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

        Raises:
            ContextTokenError: When there is not enough token space.
        """
        if tools_by_types or tools_by_names:
            fixed, bead = self._get_fixed_bead_config_with_tool(fixed=fixed, bead=bead)
        else:
            bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
            fixed = self.fixed_bead_positions if fixed == "ALL" else fixed
        
        if max_sending_token_num is None:
            max_sending_token_num = self.max_sending_token_num
        elif max_sending_token_num == "inf":
            max_sending_token_num = None
        
        if max_sending_token_num is None:
            result_inf = []
            if "START" in bead:
                result_inf.extend(self.bead_content["START"])
            
            flowing_backward_index = (
                self.flowing_bead_position - len(self._context) - 1
                if "FLOWING" in bead else None
            )
            if self._should_insert_tools_into_bead:
                assert self.tools_manager is not None
                tool_names_list = [tool.name
                    for tool in self.tools_manager.get_tools_metadata(
                        by_types=tools_by_types, by_names=tools_by_names,
                    )
                ]
            else:
                tool_names_list = []
            
            tool_names_list = cast(list[str | ToolKit], tool_names_list)
            result_inf.extend(
                self._insert_mid_bead(
                    piece_list=self._context,
                    fixed=fixed,
                    flowing_backward_index=flowing_backward_index,
                    tool_names=tool_names_list,
                    is_lenght=False,
                )
            )

            if "END" in bead:
                result_inf.extend(self.bead_content["END"])
            
            return result_inf
        
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
            trimmed_mid_content = self.trim_piece_list_by_token_num(mid_content, remaining_length)
            context_length = len(self._context)
            valid_context_length = len(trimmed_mid_content) - len(bead_content_considering_tools["FLOWING"])
            if len(trimmed_mid_content) < (
                context_length - self.flowing_bead_position + len(
                    bead_content_considering_tools["FLOWING"]
                )
            ):
                # The flowing bead should be shifted to the end.
                remaining_length -= sum(bead_lengths_considering_tools["FLOWING"])
                trimmed_messages = self.trim_piece_list_by_token_num(self._context, remaining_length)
                trimmed_mid_content = trimmed_messages + bead_content_considering_tools["FLOWING"]
                result.extend(trimmed_mid_content)
                self._flowing_bead_position = context_length
                valid_context_length = len(trimmed_messages)
                flowing_backward_index = -1
            else:
                result.extend(trimmed_mid_content)
                flowing_backward_index = (
                    self.flowing_bead_position - context_length - 1
                    if self.flowing_bead_position >= 0
                    else self.flowing_bead_position
                )
        else:
            trimmed_mid_content = self.trim_piece_list_by_token_num(self._context, remaining_length)
            result.extend(trimmed_mid_content)
            valid_context_length = len(trimmed_mid_content)
            flowing_backward_index = None

        if "FIXED" in bead:
            dynamic_fixed_info = [
                {
                    "key": position,
                    "dynaic_position": self._get_dynamic_position(
                        position=position,
                        length=len(trimmed_mid_content),
                    ),
                } for position in fixed
            ]
            sorted_fixed_info = sorted(
                dynamic_fixed_info,
                key = lambda x: (
                    x["dynaic_position"]
                    if x["dynaic_position"] >= 0
                    else len(result) - len(bead_content_considering_tools["START"]) + x["dynaic_position"]
                ),
                reverse=True,
            )
            for info in sorted_fixed_info:
                forward_position = info["dynaic_position"] if info["dynaic_position"] >= 0 else len(result) + info["dynaic_position"] + 1
                forward_position = min(max(forward_position, 0), len(result))
                result[forward_position:forward_position] = bead_content_considering_tools["FIXED"][info["key"]]
        
        if "END" in bead:
            result.extend(bead_content_considering_tools["END"])

        if not self.context_model.is_counter_modified:
            return result
        else:
            tool_names_list = cast(list[str | ToolKit], tool_names_list)
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
        fixed: list[int | str] | Literal["ALL"],
        flowing_backward_index: int | None,
        tool_names: list[str | ToolKit],
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
        if piece_token_list is not None and len(piece_token_list) == len(piece_list):
            total_token_num = sum(piece_token_list)
        else:
            total_token_num = sum(self.token_counter(piece) for piece in piece_list)
        return self.token_counter_modifier(piece_list, total_token_num)

    def validate_piece_type(self, piece: ContextPiece) -> bool:
        """Check if the type of the context piece is correct."""
        result = self.context_model.piece_type_validator(piece)
        if not result:
            raise ContextPieceTypeError(f"The type of the context piece is incorrect. Piece: {piece!r}")
        return result

    def context_append(
        self,
        piece: ContextPiece,
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str | ToolKit] | None = None,
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
        
        if tools_by_types or tools_by_names:
            fixed, bead = self._get_fixed_bead_config_with_tool(fixed=fixed, bead=bead)

        self.validate_piece_type(piece)
        if max_sending_token_num is None:
            self._context.append(piece)
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
        
        tool_names_list = cast(list[str | ToolKit], tool_names_list)
        minimal_context_token_num = self._get_minimal_context_token_num(
            pieces=[piece],
            bead=bead,
            fixed=fixed,
            tool_names=tool_names_list,
        )

        if minimal_context_token_num > max_sending_token_num:
            return False
        else:
            self._context.append(piece)
            self._piece_token_list.append(self.token_counter(piece))
            return True

    def context_extend(
        self,
        piece_list: list[ContextPiece],
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        tools_by_types: list[Literal["PERMANENT", "TEMPORARY"]] | Literal["ALL"] = "ALL",
        tools_by_names: list[str | ToolKit] | None = None,
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
       
        if tools_by_types or tools_by_names:
            fixed, bead = self._get_fixed_bead_config_with_tool(fixed=fixed, bead=bead)

        for piece in piece_list:
            self.validate_piece_type(piece)
        if max_sending_token_num is None:
            self._context.extend(piece_list)
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
        
        tool_names_list = cast(list[str | ToolKit], tool_names_list)
        minimal_context_token_num = self._get_minimal_context_token_num(
            pieces=piece_list,
            bead=bead,
            fixed=fixed,
            tool_names=tool_names_list,
        )

        if minimal_context_token_num > max_sending_token_num:
            return False
        else:
            self._piece_token_list.extend(self.token_counter(piece) for piece in piece_list)
            self._context.extend(piece_list)
            return True

    def _get_minimal_context_token_num(
        self,
        pieces: list[ContextPiece],
        bead: list[Literal["START", "FLOWING", "FIXED", "END"]] | Literal["ALL"] = "ALL",
        fixed: list[int | str] | Literal["ALL"] = "ALL",
        tool_names: list[str | ToolKit] | None = None,
    ) -> int:
        bead = ["START", "FLOWING", "FIXED", "END"] if bead == "ALL" else bead
        
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
        self._piece_token_list = [self.token_counter(piece) for piece in context]

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
        if not self.context_model.is_counter_modified:
            return piece_list
        for i in range(len(piece_list)):
            total_tokens = self._token_num_from_piece_list(
                piece_list=piece_list[i:],
                piece_token_list = piece_token_list[i:] if piece_token_list is not None else None
            )
            if total_tokens <= max_token_num:
                return piece_list[i:]
        raise ContextTokenError("There is not enough token space.")

    def _get_dynamic_position(self, position: str | int, length: int) -> int:
        """Obtain the actual absolute position dynamically based on the location and length.

        When the position is an absolute position, return it directly.
        When the position is a percentage string, calculate its actual absolute position based on the length.

        Args:
            percentage_str (str): A percentage string that ends with a '%'.
            length (int): The total length used to calculate the position.

        Returns:
            int: The calculated integer position with rounding applied.

        Raises:
            ValueError:
                If the input string is not a valid percentage string or if the length
                is not a positive integer.
        """
        if isinstance(position, int):
            return position

        percentage_str = position

        if not percentage_str.endswith('%'):
            raise ValueError("Percentage string must end with '%'")

        try:
            percentage_value = float(percentage_str.rstrip('%'))
        except ValueError:
            raise ValueError("The string without '%' must be convertible to a float")

        if not isinstance(length, int) or length <= 0:
            raise ValueError("Length must be a positive integer")

        position = round(percentage_value * length / 100)
        position = min(max(position, 0), length)

        return position


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
