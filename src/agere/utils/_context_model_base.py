from abc import ABCMeta, abstractmethod
from typing import Generic, TypeVar


ContextPiece = TypeVar("ContextPiece")


class ContextModelBase(Generic[ContextPiece], metaclass=ABCMeta):

    @property
    @abstractmethod
    def context_model_name(self) -> str:
        ...
    
    @abstractmethod
    def token_counter(self, context_piece: ContextPiece) -> int:
        """Specify the method for calculating the number of tokens for each context piece."""
        ...

    def token_counter_modifier(self, context_piece_list: list[ContextPiece], total_token_num: int) -> int:
        """Specify the method for calculating the total number of tokens for a list of context pieces.
        
        If the sum of tokens for all individual context pieces does not equal the total token count,
        this method can provide a way to compensate for the token calculation discrepancy by the
        token_counter.
        It receives a list of context pieces as the first argument, and the sum of the tokens of
        these pieces as the second argument.
        It is only necessary when the total number of tokens is not equal to the sum of the tokens
        for each piece.
        """ 
        return total_token_num

    def piece_type_validator(self, context_piece: ContextPiece) -> bool:
        """Specify the method for checking the type of the context piece.
        
        If such a method is designated, a type check will be performed on each context piece being
        written to ensure it is of a legitimate context piece type.
        """
        return True

    @property
    def is_counter_modified(self) -> bool:
        """Return whether the token counter needs to be modified.

        Return:
            True when modification is needed, otherwise return False.
        """
        current_token_counter_modifier_method = self.__class__.token_counter_modifier
        base_token_counter_modifier_method = ContextModelBase.token_counter_modifier
        return current_token_counter_modifier_method != base_token_counter_modifier_method
