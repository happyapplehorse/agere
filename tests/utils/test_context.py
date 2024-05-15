import pytest
from typing import TypedDict

from agere.utils.context import Context, ContextPieceTypeError, _find_position
from agere.utils.context_models import OpenaiContextModel
from agere.utils._context_model_base import ContextModelBase


@pytest.mark.parametrize(
    "lst, num, expected_pos",
    [
        ([1, 2, 3, 4, 5], 8, 4),
        ([2, 0, 5, 1, 3, 2, 1, 0, 4], 9, 5),
        ([2, 0, 5, 1, 3, 2, 1, 0, 4], 2, 9),
        ([2, 0, 5, 1, 3, 2, 1, 0, 4], 20, 0),
    ]
)
def test_find_position(lst: str, num: int, expected_pos: int):
    # Assert
    assert _find_position(lst, num) == expected_pos


class CustomContextPiece(TypedDict):
    role: str
    content: str


class TestContext:

    def piece_token_counter(self, context_piece) -> int:
        # Assume the number of tokens is equal to the number of characters.
        return len(context_piece["content"])

    def context_token_counter_modifier(self, context_piece_list: list, total_sum: int) -> int:
        # Assume that each context piece occupies an additional token.
        return len(context_piece_list) + total_sum

    class CustomContextModel(ContextModelBase):
        def context_model_name(self) -> str:
            return "CUSTOM"

        def token_counter(self, context_piece: CustomContextPiece) -> int:
            # Assume the number of tokens is equal to the number of characters.
            return len(context_piece["content"])

        def token_counter_modifier(
            self,
            context_piece_list: list[CustomContextPiece],
            total_token_num: int,
        ) -> int:
            # Assume that each context piece occupies an additional token.
            return len(context_piece_list) + total_token_num

        def piece_type_validator(self, context_piece: CustomContextPiece) -> bool:
            required_keys = {"role", "content"}
            return isinstance(context_piece, dict) and required_keys <= context_piece.keys()

    @pytest.fixture
    def openai_context(self) -> Context[dict[str, str]]:
        return Context(
            context_model=OpenaiContextModel(
                token_counter=self.piece_token_counter,
                token_counter_modifier=self.context_token_counter_modifier,
            ),
            token_window=100,
            max_sending_token_num=50,
        )
    
    @pytest.fixture
    def custom_context(self) -> Context[CustomContextPiece]:
        return Context[CustomContextPiece](
            context_model=self.CustomContextModel(),
            token_window=100,
            max_sending_token_num=50,
        )

    @pytest.fixture
    def context_piece_list(self) -> list[CustomContextPiece]:
        piece_list = []
        for i in range(1, 11):
            piece_list.extend(
                [
                    {
                        "role": "user",
                        "content": f"Hi-{i}.",
                    },
                    {
                        "role": "assistant",
                        "content": f"Hello-{i}.",
                    },
                ]
            )
        return piece_list

    @pytest.fixture
    def bead_example(self) -> list[CustomContextPiece]:
        return [
            {
                "role": "system",
                "content": "This is a bead system message.",
            }
        ]

    def test_piece_type_validate(self, openai_context: Context, custom_context: Context):
        # Assert
        with pytest.raises(ContextPieceTypeError):
            openai_context.context_append(piece={"role": "user"})
        with pytest.raises(ContextPieceTypeError):
            custom_context.context_append(piece={"content": "Hi."})

    def test_context_append(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Setup
        short_piece = {
            "role": "user",
            "content": "Hi.",
        }
        too_long_piece = {
            "role": "assistant",
            "content": "Hi." * 20,
        }

        custom_context.bead_update(new_beads=bead_example, which="START")
        custom_context.bead_update(new_beads=bead_example, which="END")
        custom_context.bead_update(new_beads=bead_example, which="FLOWING")
        custom_context.bead_update(new_beads=bead_example, which="FIXED", fixed=-1)

        # Action
        state = custom_context.context_append(piece=short_piece)

        # Assert
        assert state is False

        # Action
        state = custom_context.context_append(piece=short_piece, max_sending_token_num=150)
        
        # Assert
        assert state is True
        assert custom_context.context == [{"role": "user", "content": "Hi."}]

        # Action
        state = custom_context.context_append(piece=too_long_piece)

        # Assert
        assert state is False
        assert custom_context.context == [{"role": "user", "content": "Hi."}]
    
    def test_context_extend(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Setup
        short_piece = {
            "role": "user",
            "content": "Hi.",
        }

        custom_context.bead_update(new_beads=bead_example, which="START")
        custom_context.bead_update(new_beads=bead_example, which="END")
        custom_context.bead_update(new_beads=bead_example, which="FLOWING")
        custom_context.bead_update(new_beads=bead_example, which="FIXED", fixed=-1)

        # Action
        state = custom_context.context_extend(piece_list=[short_piece])

        # Assert
        assert state is False

        # Action
        state = custom_context.context_extend(piece_list=[short_piece], max_sending_token_num=150)

        # Assert
        assert state is True
        assert custom_context.context == [{"role": "user", "content": "Hi."}]

        # Action
        state = custom_context.context_extend(piece_list = [short_piece] * 20)

        # Assert
        assert state is False
        assert custom_context.context == [{"role": "user", "content": "Hi."}]

    def test_context_update(self, custom_context: Context, context_piece_list: list[CustomContextPiece]):
        # Setup
        piece = {
            "role": "user",
            "content": "Hi.",
        }

        # Action
        state = custom_context.context_append(piece=piece)

        # Assert
        assert custom_context.context == [{"role": "user", "content": "Hi."}]
        
        # Action
        state = custom_context.context_update(context=context_piece_list)

        # Assert
        assert custom_context.context == context_piece_list
    

    def test_bead_content(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Setup
        custom_context.bead_update(new_beads=bead_example, which="START")
        custom_context.bead_update(new_beads=bead_example, which="END")
        custom_context.bead_update(new_beads=bead_example, which="FLOWING")
        custom_context.bead_update(new_beads=bead_example, which="FIXED", fixed=-1)

        expected_bead_content = {
            "START": [
                {
                    "role": "system",
                    "content": "This is a bead system message.",
                },
            ],
            "FLOWING": [
                {
                    "role": "system",
                    "content": "This is a bead system message.",
                },
            ],
            "FIXED": {
                -1: [
                    {
                        "role": "system",
                        "content": "This is a bead system message.",
                    },
                ],
            },
            "END": [
                {
                    "role": "system",
                    "content": "This is a bead system message.",
                },
            ],
        }
        expected_copied_bead_content_after_modified = {
            "START": [
                {
                    "role": "system",
                    "content": "XXXX",
                },
            ],
            "FLOWING": [
                {
                    "role": "system",
                    "content": "XXXX",
                },
            ],
            "FIXED": {
                -1: [
                    {
                        "role": "system",
                        "content": "XXXX",
                    },
                ],
            },
            "END": [
                {
                    "role": "system",
                    "content": "XXXX",
                },
            ],
        }

        # Assert
        assert custom_context.bead_content == expected_bead_content
        
        # Action
        copied_bead_content = custom_context.bead_content
        copied_bead_content["START"][0]["content"] = "XXXX"

        # Assert
        assert copied_bead_content == expected_copied_bead_content_after_modified
        assert custom_context.bead_content == expected_bead_content

    def test_token_num(self, custom_context: Context, context_piece_list: list[CustomContextPiece]):
        # Setup
        state = custom_context.context_extend(piece_list=context_piece_list, max_sending_token_num=200)

        # Action
        token_num = custom_context.token_num

        # Assert
        assert token_num == 152

    def test_context_ratio(
        self,
        custom_context: Context,
        bead_example: list[CustomContextPiece],
        context_piece_list: list[CustomContextPiece]
    ):
        # Setup
        custom_context.max_sending_token_num = 200
        custom_context.bead_update(new_beads=bead_example, which="START")
        custom_context.bead_update(new_beads=bead_example, which="END")
        custom_context.bead_update(new_beads=bead_example, which="FLOWING")
        custom_context.bead_update(new_beads=bead_example, which="FIXED", fixed=-1)
        custom_context.context_extend(piece_list=context_piece_list[:2])

        # Action
        context_ratio_1 = custom_context.context_ratio()
        context_ratio_2 = custom_context.context_ratio(context=False)
        context_ratio_3 = custom_context.context_ratio(bead=["START", "FIXED"])
        context_ratio_4 = custom_context.context_ratio(bead=["FIXED", "END"], fixed=[])
        context_ratio_5 = custom_context.context_ratio(bead=["START", "FIXED", "FLOWING"], max_sending_token_num=300)

        # Assert
        assert context_ratio_1 == (15 + 31*4) / 200
        assert context_ratio_2 == (31*4) / 200
        assert context_ratio_3 == (15 + 31*2) / 200
        assert context_ratio_4 == (15 + 31) / 200
        assert context_ratio_5 == (15 + 31*3) / 300

    def test_bead_append(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Action
        custom_context.bead_append(bead=bead_example[0], which="START")
        custom_context.bead_append(bead=bead_example[0], which="FLOWING")
        custom_context.bead_append(bead=bead_example[0], which="FIXED", fixed=2)
        custom_context.bead_append(bead=bead_example[0], which="END")

        # Assert
        assert custom_context.bead_content == {
            "START": bead_example,
            "FLOWING": bead_example,
            "FIXED": {
                2: bead_example,
            },
            "END": bead_example,
        }
        
        with pytest.raises(ValueError):
            custom_context.bead_append(bead=bead_example[0], which="FIXED")
    
    def test_bead_extend(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Action
        custom_context.bead_extend(beads=bead_example, which="START")
        custom_context.bead_extend(beads=bead_example, which="FLOWING")
        custom_context.bead_extend(beads=bead_example, which="FIXED", fixed=2)
        custom_context.bead_extend(beads=bead_example, which="END")

        # Assert
        assert custom_context.bead_content == {
            "START": bead_example,
            "FLOWING": bead_example,
            "FIXED": {
                2: bead_example,
            },
            "END": bead_example,
        }

        with pytest.raises(ValueError):
            custom_context.bead_extend(beads=bead_example, which="FIXED")
    
    def test_bead_update(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Action
        custom_context.bead_extend(beads = bead_example * 2, which="START")
        custom_context.bead_extend(beads = bead_example * 2, which="FLOWING")
        custom_context.bead_extend(beads = bead_example * 2, which="FIXED", fixed=2)
        custom_context.bead_extend(beads = bead_example * 2, which="END")
        custom_context.bead_update(new_beads=bead_example, which="START")
        custom_context.bead_update(new_beads=bead_example, which="FLOWING")
        custom_context.bead_update(new_beads=bead_example, which="FIXED", fixed=2)
        custom_context.bead_update(new_beads=bead_example, which="END")

        # Assert
        assert custom_context.bead_content == {
            "START": bead_example,
            "FLOWING": bead_example,
            "FIXED": {
                2: bead_example,
            },
            "END": bead_example,
        }

        with pytest.raises(ValueError):
            custom_context.bead_update(new_beads=bead_example, which="FIXED")
    
    def test_bead_piece_overwrite(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Setup
        new_bead = {
            "role": "system",
            "content": "New bead."
        }

        # Action
        custom_context.bead_extend(beads = bead_example * 2, which="FLOWING")
        custom_context.bead_extend(beads = bead_example * 2, which="FIXED", fixed=-1)
        custom_context.bead_piece_overwrite(bead=new_bead, which="FLOWING", index=0)
        custom_context.bead_piece_overwrite(bead=new_bead, which="FIXED", fixed=-1)

        # Assert
        assert custom_context.bead_content == {
            "START": [],
            "FLOWING": [
                {
                    "role": "system",
                    "content": "New bead.",
                },
                {
                    "role": "system",
                    "content": "This is a bead system message.",
                },
            ],
            "FIXED": {
                -1: [
                    {
                        "role": "system",
                        "content": "This is a bead system message.",
                    },
                    {
                        "role": "system",
                        "content": "New bead.",
                    },
                ],
            },
            "END": [],
        }

        with pytest.raises(ValueError):
            custom_context.bead_piece_overwrite(bead=new_bead, which="FIXED")

    def test_bead_lengths(self, custom_context: Context, bead_example: list[CustomContextPiece]):
        # Setup
        custom_context.bead_extend(beads = bead_example * 2, which="START")
        custom_context.bead_extend(beads = bead_example * 2, which="FLOWING")
        custom_context.bead_extend(beads = bead_example * 2, which="FIXED", fixed=-1)
        custom_context.bead_extend(beads = bead_example * 2, which="END")

        # Assert
        assert custom_context.bead_lengths == {
            "START": [30, 30],
            "FLOWING": [30, 30],
            "FIXED": {
                -1: [30, 30],
            },
            "END": [30, 30],
        }

    def test_fixed_bead_positions(
        self,
        custom_context: Context,
        bead_example: list[CustomContextPiece],
    ):
        # Action
        custom_context.bead_extend(beads=bead_example, which="FIXED", fixed=-1)
        custom_context.bead_extend(beads=bead_example, which="FIXED", fixed=1)
        custom_context.bead_extend(beads=bead_example, which="FIXED", fixed=5)
        custom_context.bead_extend(beads=bead_example, which="FIXED", fixed=-3)

        # Assert
        assert set(custom_context.fixed_bead_positions) == {-1, 1, 5, -3}

    def test_piece_token_list(self, custom_context: Context, context_piece_list: list[CustomContextPiece]):
        # Action
        custom_context.context_extend(context_piece_list, max_sending_token_num=200)

        # Assert
        assert custom_context.piece_token_list == [5, 8] * 9 + [6, 9]

    def test_validate_piece_type(self, custom_context: Context, openai_context: Context):
        # Setup
        right_piece = {
            "role": "user",
            "content": "Content."
        }
        wrong_piece = {
            "who": "user",
            "content": "Content."
        }

        # Assert
        assert custom_context.validate_piece_type(piece=right_piece) is True
        with pytest.raises(ContextPieceTypeError):
            assert custom_context.validate_piece_type(piece=wrong_piece) is False
        assert openai_context.validate_piece_type(piece=right_piece) is True
        with pytest.raises(ContextPieceTypeError):
            assert openai_context.validate_piece_type(piece=wrong_piece) is False

    def test_shift_flowing_bead(
        self,
        custom_context: Context,
        context_piece_list: list[CustomContextPiece],
        bead_example: list[CustomContextPiece],
    ):
        # Setup
        custom_context.context_update(context_piece_list)
        custom_context.bead_extend(beads=bead_example, which="FLOWING")

        # Assert
        assert custom_context.flowing_bead_position == 0

        # Action
        custom_context.shift_flowing_bead()

        # Assert
        assert custom_context.flowing_bead_position == 20

    def test_trim_piece_list_by_token_num(self, custom_context: Context, context_piece_list: list[CustomContextPiece]):
        # Action
        trimmed_piece_list = custom_context.trim_piece_list_by_token_num(
            piece_list=context_piece_list,
            max_token_num=100,
            modifier=False,
        )

        # Assert
        assert trimmed_piece_list == context_piece_list[6:]
        
        # Action
        trimmed_piece_list = custom_context.trim_piece_list_by_token_num(
            piece_list=context_piece_list,
            max_token_num=100,
            modifier=True,
        )

        # Assert
        assert trimmed_piece_list == context_piece_list[8:]
    
    def test_context_sending(self, custom_context: Context, context_piece_list: list[CustomContextPiece]):
        # Setup
        start_beads = [
            {
                "role": "system",
                "content": "Start bead 0."
            },
        ]  # length = [14]
        flowing_beads = [
            {
                "role": "system",
                "content": "Flowing bead 0."
            },
            {
                "role": "system",
                "content": "Flowing bead 1."
            },
        ]  # length = [16, 16]
        fixed_beads = [
            {
                "role": "system",
                "content": "Fixed bead 0."
            },
        ]  # length = [14]
        end_beads = [
            {
                "role": "system",
                "content": "End bead 0."
            },
            {
                "role": "system",
                "content": "End bead 1."
            },
        ]  # length = [12, 12]
        custom_context.bead_extend(beads=start_beads, which="START")
        custom_context.bead_extend(beads=flowing_beads, which="FLOWING")
        custom_context.bead_extend(beads=fixed_beads, which="FIXED", fixed=-2)
        custom_context.bead_extend(beads=end_beads, which="END")
        custom_context.max_sending_token_num = 150

        # Action
        for piece in context_piece_list:
            custom_context.context_append(piece)

        # Assert
        assert custom_context.flowing_bead_position == 0
        assert custom_context.context_sending() == (
            start_beads
            + context_piece_list[12:]
            + flowing_beads[:-1]
            + fixed_beads
            + flowing_beads[-1:]
            + end_beads
        )
        assert custom_context.context_sending(bead=["START", "FIXED", "END"]) == (
            start_beads
            + context_piece_list[8:-1]
            + fixed_beads
            + context_piece_list[-1:]
            + end_beads
        )

        # Action
        custom_context.bead_extend(beads=fixed_beads, which="FIXED", fixed="50%")
        
        # Assert
        assert custom_context.context_sending() == (
            start_beads
            + context_piece_list[14:18]
            + fixed_beads  # 50%
            + context_piece_list[18:]
            + flowing_beads[:-1]
            + fixed_beads
            + flowing_beads[-1:]
            + end_beads
        )

        # Action
        new_context_piece = {
            "role": "user",
            "content": "Hi-11."
        }
        custom_context.context_append(piece=new_context_piece)

        # Assert
        assert custom_context.context_sending() == (
            start_beads
            + context_piece_list[15:19]
            + fixed_beads  # 50%
            + context_piece_list[19:]
            + flowing_beads
            + fixed_beads
            + [new_context_piece]
            + end_beads
        )
