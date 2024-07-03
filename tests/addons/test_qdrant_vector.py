import pytest
from unittest.mock import Mock, patch

from agere.addons.qdrant_vector import AsyncQdrantVector, models


@pytest.fixture
def async_qdrant_client() -> AsyncQdrantVector:
    return AsyncQdrantVector(position=":memory:", position_type="memory")

def test_set_embedding_model(async_qdrant_client: AsyncQdrantVector):
    # Action
    with patch("agere.addons.qdrant_vector.AsyncQdrantClient.set_model") as mock_set_model:
        async_qdrant_client.set_embedding_model("model")

    # Assert
    mock_set_model.assert_called_with("model")

async def test_create_collection(async_qdrant_client: AsyncQdrantVector):
    # Action
    await async_qdrant_client.create_collection("test_collection")
    all_collections = await async_qdrant_client.get_all_collections()
    
    # Assert
    assert  all_collections == ["test_collection"]

def test_default_vector_size(async_qdrant_client: AsyncQdrantVector):
    # Action
    size = async_qdrant_client.default_vector_size
    
    # Assert
    assert isinstance(size, int)

def test_split(async_qdrant_client: AsyncQdrantVector):
    # Setup
    text_example = "This is a text example."
    # Action
    text = async_qdrant_client.split(text_example)

    # Assert
    assert list(text) == [text_example]

    # Setup
    text_splitter = Mock()
    async_qdrant_client.text_splitter = text_splitter
    
    # Action
    text = async_qdrant_client.split(text_example)

    # Assert
    text_splitter.split.assert_called_with(text_example)

async def test_recreate_collection(async_qdrant_client: AsyncQdrantVector):
    # Setup
    await async_qdrant_client.create_collection(
        "test_collection",
        vectors_config=models.VectorParams(
            size=100,
            distance=models.Distance.COSINE,
        ),
    )

    # Assert
    info = await async_qdrant_client.get_collection("test_collection")
    assert info.config.params.vectors.size == 100  # type: ignore
    
    # Action
    await async_qdrant_client.recreate_collection(
        "test_collection",
        vectors_config=models.VectorParams(
            size=200,
            distance=models.Distance.COSINE,
        ),
    )
    
    # Assert
    info = await async_qdrant_client.get_collection("test_collection")
    assert info.config.params.vectors.size == 200  # type: ignore
    
async def test_delete_collection(async_qdrant_client: AsyncQdrantVector):
    # Action
    await async_qdrant_client.create_collection("test_collection")
    all_collections = await async_qdrant_client.get_all_collections()
    
    # Assert
    assert  all_collections== ["test_collection"]
    
    # Action
    await async_qdrant_client.delete_collection("test_collection")
    all_collections = await async_qdrant_client.get_all_collections()
    
    # Assert
    assert  all_collections== []

async def test_update_collection(async_qdrant_client: AsyncQdrantVector):
    # Action
    with patch("agere.addons.qdrant_vector.AsyncQdrantClient.update_collection") as mock_update_collection:
        await async_qdrant_client.update_collection("test_collection", vectors_config=None)

    # Assert
    mock_update_collection.assert_called_with(collection_name="test_collection", vectors_config=None)

async def test_get_all_collection(async_qdrant_client: AsyncQdrantVector):
    # Action
    await async_qdrant_client.create_collection("test_collection_1")
    await async_qdrant_client.create_collection("test_collection_2")
    all_collections = await async_qdrant_client.get_all_collections()
    
    # Assert
    assert  set(all_collections) == {"test_collection_1", "test_collection_2"}

async def test_dose_collection_exist(async_qdrant_client: AsyncQdrantVector):
    # Setup
    await async_qdrant_client.create_collection("test_collection")

    # Action
    yes = await async_qdrant_client.does_collection_exist("test_collection")
    no = await async_qdrant_client.does_collection_exist("test_collection_1")

    # Assert
    assert yes is True
    assert no is False

async def test_get_collection_info(async_qdrant_client: AsyncQdrantVector):
    # Action
    await async_qdrant_client.create_collection(
        "test_collection",
        vectors_config=models.VectorParams(
            size=100,
            distance=models.Distance.COSINE,
        ),
    )
    info = await async_qdrant_client.get_collection_info("test_collection")

    # Assert
    assert info.config.params.vectors.size == 100  # type: ignore

async def test_add_and_count(async_qdrant_client: AsyncQdrantVector):
    # Setup
    await async_qdrant_client.create_collection(collection_name="test_collection")
    documents = [
        "Thomas's horse is green.",
        "Thomas has a red apple.",
    ]

    # Action
    await async_qdrant_client.add(
        collection_name="test_collection",
        documents=documents,
    )

    # Assert
    count = await async_qdrant_client.count("test_collection")
    assert count == 2
    
async def test_query(async_qdrant_client: AsyncQdrantVector):
    # Setup
    await async_qdrant_client.create_collection(collection_name="test_collection")
    documents = [
        "Thomas's horse is green.",
        "Thomas has a red apple.",
    ]
    names = [
        "horse",
        "apple",
    ]
    kinds = ["test", "test"]
    create_time = [
        "2024-05-18T15:12:00Z",
        "2024-05-18T15:12:00Z",
    ]
    await async_qdrant_client.add(
        collection_name="test_collection",
        documents=documents,
        names=names,
        kinds=kinds,
        created_datetimes=create_time,  # type: ignore
        updated_datetimes=create_time,  # type: ignore
    )

    # Action
    result = await async_qdrant_client.query(
        collection_name="test_collection",
        query_text="What the color is thomas's horse?",
    )

    # Assert
    assert result == documents
    
    # Action
    result = await async_qdrant_client.query(
        collection_name="test_collection",
        query_text="Thomas has something red, do you know what it is?",
    )

    # Assert
    assert result == documents[::-1]
    
    # Action
    result = await async_qdrant_client.query(
        collection_name="test_collection",
        query_text="What the color is thomas's horse?",
        limit=1,
        return_text=False,
    )
    assert result[0].metadata == {  # type: ignore
        'document': "Thomas's horse is green.",
        'name': 'horse',
        'category': None,
        'kind': 'test',
        'created_datetime': '2024-05-18T15:12:00Z',
        'updated_datetime': '2024-05-18T15:12:00Z',
    }

async def test_query_batch(async_qdrant_client: AsyncQdrantVector):
    # Setup
    await async_qdrant_client.create_collection(collection_name="test_collection")
    documents = [
        "Thomas's horse is green.",
        "Thomas has a red apple.",
        "Beijing is the captial of China."
    ]
    names = [
        "horse",
        "apple",
        "city",
    ]
    categories = [
        "cat_1",
        "cat_1",
        "cat_2"
    ]
    kinds = ["test", "test", "test"]
    create_time = [
        "2024-05-18T15:12:00Z",
        "2024-05-18T15:12:00Z",
        "2024-05-18T15:12:00Z",
    ]
    await async_qdrant_client.add(
        collection_name="test_collection",
        documents=documents,
        names=names,
        categories=categories,
        kinds=kinds,
        created_datetimes=create_time,  # type: ignore
        updated_datetimes=create_time,  # type: ignore
    )

    # Action
    result = await async_qdrant_client.query_batch(
        collection_name="test_collection",
        query_texts=[
            "What the color is thomas's horse?",
            "Where is the captial of China?",
        ],
        limit=1,
    )

    # Assert
    assert result == [
        ["Thomas's horse is green."],
        ["Beijing is the captial of China."],
    ]
    
    # Action
    result = await async_qdrant_client.query_batch(
        collection_name="test_collection",
        query_texts=[
            "What the color is thomas's horse?",
            "Where is the captial of China?",
        ],
        limit=1,
        return_text=False
    )

    # Assert
    assert result[0][0].metadata == {  # type: ignore
        'document': "Thomas's horse is green.",
        'name': 'horse',
        'category': 'cat_1',
        'kind': 'test',
        'created_datetime': '2024-05-18T15:12:00Z',
        'updated_datetime': '2024-05-18T15:12:00Z',
    }

async def test_scroll(async_qdrant_client: AsyncQdrantVector):
    # Setup
    documents = [
        "Thomas's horse is green.",
        "Thomas has a red apple.",
        "Beijing is the captial of China."
    ]
    names = [
        "horse",
        "apple",
        "city",
    ]
    categories = [
        "cat_1",
        "cat_1",
        "cat_2"
    ]
    kinds = ["test", "test", "test"]
    create_time = [
        "2024-05-18T15:00:00Z",
        "2024-05-18T16:00:00Z",
        "2024-05-18T17:00:00Z",
    ]
    await async_qdrant_client.add(
        collection_name="test_collection",
        documents=documents,
        names=names,
        categories=categories,
        kinds=kinds,
        created_datetimes=create_time,  # type: ignore
        updated_datetimes=create_time,  # type: ignore
    )

    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
    )

    # Assert
    assert len(result[0]) == 3
    
    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
        scroll_filter=async_qdrant_client.metadata_filter(
            names=['horse', 'city'],
        )
    )
    names = {record.payload["name"] for record in result[0] if record.payload is not None}

    # Assert
    assert names == {'horse', 'city'}
    
    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
        scroll_filter=async_qdrant_client.metadata_filter(
            categories=['cat_1'],
            kinds=['test'],
        )
    )
    names = {record.payload["name"] for record in result[0] if record.payload is not None}
    
    # Assert
    assert names == {'horse', 'apple'}
    
    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
        scroll_filter=async_qdrant_client.metadata_filter(
            kinds=['test'],
            created_datetime_range=("2024-05-18T12:00:00Z", "2024-05-18T17:30:00Z"),  # type: ignore
            updated_datetime_range=("2024-05-18T14:00:00Z", "2024-05-18T16:30:00Z"),  # type: ignore
        )
    )
    names = {record.payload["name"] for record in result[0] if record.payload is not None}
    
    # Assert
    assert names == {'horse', 'apple'}
    
    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
        scroll_filter=async_qdrant_client.metadata_filter(
            kinds=['test'],
            created_datetime_range=("2024-05-18T12:00:00Z", "2024-05-18T17:30:00Z"),  # type: ignore
            updated_datetime_range=("2024-05-18T14:00:00Z", "2024-05-18T16:30:00Z"),  # type: ignore
            document_texts=['is'],
        ),
    )
    names = {record.payload["name"] for record in result[0] if record.payload is not None}
    
    # Assert
    assert names == {'horse'}
    
    # Action
    result = await async_qdrant_client.scroll(
        collection_name="test_collection",
        scroll_filter=async_qdrant_client.metadata_filter(
            names=['horse', 'city'],
            categories=['cat_1', 'cat_2'],
            kinds=['test'],
            created_datetime_range=("2024-05-18T12:00:00Z", "2024-05-18T18:30:00Z"),  # type: ignore
            updated_datetime_range=("2024-05-18T16:00:00Z", "2024-05-18T18:30:00Z"),  # type: ignore
            document_texts=['ap'],
        ),
    )
    names = {record.payload["name"] for record in result[0] if record.payload is not None}
    
    # Assert
    assert names == {'city'}

async def test_delete(async_qdrant_client: AsyncQdrantVector):
    # Setup
    documents = [
        "Thomas's horse is green.",
        "Thomas has a red apple.",
        "Beijing is the captial of China."
    ]
    names = [
        "horse",
        "apple",
        "city",
    ]
    categories = [
        "cat_1",
        "cat_1",
        "cat_2"
    ]
    kinds = ["test", "test", "test"]
    create_time = [
        "2024-05-18T15:00:00Z",
        "2024-05-18T16:00:00Z",
        "2024-05-18T17:00:00Z",
    ]
    await async_qdrant_client.add(
        collection_name="test_collection",
        documents=documents,
        names=names,
        categories=categories,
        kinds=kinds,
        created_datetimes=create_time,  # type: ignore
        updated_datetimes=create_time,  # type: ignore
    )

    # Assert
    count = await async_qdrant_client.count("test_collection")
    assert count == 3

    # Action
    await async_qdrant_client.delete(
        collection_name="test_collection",
        filter=async_qdrant_client.metadata_filter(
            categories=["cat_1"]
        ),
    )

    # Assert
    count = await async_qdrant_client.count("test_collection")
    assert count == 1
    
    # Action
    await async_qdrant_client.delete(
        collection_name="test_collection",
        filter=async_qdrant_client.metadata_filter(
            names=["horse", "city"]
        ),
    )
    
    # Assert
    count = await async_qdrant_client.count("test_collection")
    assert count == 0
