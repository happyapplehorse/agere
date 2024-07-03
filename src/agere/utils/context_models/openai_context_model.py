from typing import Callable, Generic

from .._context_model_base import ContextModelBase, ContextPiece


class OpenaiContextModel(ContextModelBase, Generic[ContextPiece]):
    
    def __init__(
        self,
        token_counter: Callable[[ContextPiece], int],
        token_counter_modifier: Callable[[list[ContextPiece], int], int] | None = None,
    ):
        """Initialize a OpenaiContextModel.

        Args:
            token_counter: Specify the method for calculating the number of tokens for each context piece.
            token_counter_modifier:
                Specify the method for calculating the total number of tokens for a list of context pieces.
                If the sum of tokens for all individual context pieces does not equal the total token count,
                this method can provide a way to compensate for the token calculation discrepancy by the
                token_counter.
                It receives a list of context pieces as the first argument, and the sum of the tokens of
                these pieces as the second argument.
                It is only necessary when the total number of tokens is not equal to the sum of the tokens
                for each piece.
        """
        self._token_counter = token_counter
        self._token_counter_modifier = token_counter_modifier

    @property
    def context_model_name(self) -> str:
        """The name of the context model."""
        return "OPENAI"

    def token_counter(self, context_piece: ContextPiece) -> int:
        """Calculate the token number of the given context piece."""
        if self._token_counter is None:
            raise NotImplementedError("'token_counter' is not specified.")
        return self._token_counter(context_piece)
    
    def token_counter_modifier(self, context_piece_list: list[ContextPiece], total_token_num: int) -> int:
        """Used to adjust the total token number in a list.

        Args:
            piece_list: A list of context piece to calculate token number for.
            total_token_num: The simple sum of the token number for each piece in the piece list.

        Returns:
            The actual token number corresponding to the piece list.
        """
        if self._token_counter_modifier is None:
            return total_token_num
        return self._token_counter_modifier(context_piece_list, total_token_num)
    
    def piece_type_validator(self, context_piece: ContextPiece) -> bool:
        """Check if the context_piece is a valid openai message piece."""
        required_keys = {'role', 'content'}
        return isinstance(context_piece, dict) and required_keys <= context_piece.keys()
    
    @property
    def is_counter_modified(self) -> bool:
        """Return whether the token counter needs to be modified.

        Returns:
            True when modification is needed, otherwise return False.
        """
        return False if self._token_counter_modifier is None else True
