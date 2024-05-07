from __future__ import annotations
from datetime import datetime, timezone
from itertools import cycle
from logging import Logger
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Iterable,
    Sequence,
)
try:
    from qdrant_client import AsyncQdrantClient, models
except ImportError:
    _QDRANT_CLIENT_INSTALLED = False
else:
    _QDRANT_CLIENT_INSTALLED = True

try:
    import fastembed
except ImportError:
    _FASTEMBED_INSTALLED = False
else:
    _FASTEMBED_INSTALLED = True

from ..commander._null_logger import get_null_logger


if TYPE_CHECKING:
    from qdrant_client.models import Distance, ExtendedPointId, Filter
    from qdrant_client.conversions import common_types as types
    from qdrant_client.fastembed_common import QueryResponse


def _import_fastembed() -> None:
    if _FASTEMBED_INSTALLED is False:
        raise ImportError(
            "Could not import fastembed. Please install"
            "it with 'pip install fastembed'."
        )

def _import_qdrant_client() -> None:
    if _QDRANT_CLIENT_INSTALLED is False:
        raise ImportError(
            "Could not import qdrant_client. Please install"
            "it with 'pip install qdrant-client'."
        )


class QdrantVector:

    def __init__(
        self,
        position: str,
        position_type: Literal["memory", "disk", "server", "cloud"],
        api_key: str | None = None,
        vector_size: int | None = None,
        logger: Logger | None = None,
    ):
        _import_qdrant_client()
        self._default_vector_size = vector_size
        self.logger = logger or get_null_logger()
        if position_type == "memory":
            self.async_qdrant_client = AsyncQdrantClient(location=":memory:")
        elif position_type == "disk":
            self.async_qdrant_client = AsyncQdrantClient(path=position)
        elif position_type == "server":
            if api_key:
                self.async_qdrant_client = AsyncQdrantClient(url=position, api_key=api_key)
            else:
                self.async_qdrant_client = AsyncQdrantClient(url=position)
        elif position_type == "cloud":
            self.async_qdrant_client = AsyncQdrantClient(url=position, api_key=api_key)

    def set_embedding_model(self, embedding_model_name: str) -> None:
        _import_fastembed()
        self.async_qdrant_client.set_model(embedding_model_name)

    @property
    def default_vector_size(self) -> int:
        _import_fastembed()
        return self._default_vector_size or self._get_fastembed_model_params(
            model_name=self.async_qdrant_client.embedding_model_name
        )[0]

    def _get_fastembed_model_params(self, model_name: str) -> tuple[int, models.Distance]:
        _import_fastembed()
        from qdrant_client.async_qdrant_fastembed import SUPPORTED_EMBEDDING_MODELS
        if model_name not in SUPPORTED_EMBEDDING_MODELS:
            raise ValueError(
                f"Unsupported embedding model: {model_name}. Supported models: {SUPPORTED_EMBEDDING_MODELS}"
            )
        return SUPPORTED_EMBEDDING_MODELS[model_name]

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int | None = None,
        distance: Distance | None = None,
        init_from_collection_name: str | None = None,
    ) -> bool:
        """Creates empty collection with given parameters.

        Arguments:
            collection_name: The name of the collection to create.
            vector_size: The size of the vector.
            distance: The distance metric to use. (default: {"Cosine"})
            init_from_collection_name: Use data stored in another collection to initialize this collection.

        Returns:
            Operation result.
        """
        return await self.async_qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size or self.default_vector_size,
                distance=distance or self._get_fastembed_model_params(
                    model_name=self.async_qdrant_client.embedding_model_name
                )[1],
            ),
            init_from=models.InitFrom(
                collection=init_from_collection_name
            ) if init_from_collection_name is not None else None,
        )

    async def recreate_collection(
        self,
        collection_name: str,
        vector_size: int | None = None,
        distance: Distance | None = None,
    ) -> bool:
        """Delete and create empty collection with given parameters.

        Arguments:
            collection_name: The name of the collection to create.
            vector_size: The size of the vector.
            distance: The distance metric to use. (default: {"Cosine"})

        Returns:
            Operation result.
        """
        return await self.async_qdrant_client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size or self.default_vector_size,
                distance=distance or self._get_fastembed_model_params(
                    model_name=self.async_qdrant_client.embedding_model_name
                )[1],
            ),
        )

    async def get_collection(self, collection_name: str) -> types.CollectionInfo:
        """Gets the a collections based upon collection name.

        Returns:
            CollectionInfo: Collection Information from Qdrant about collection.
        """
        collection_info = await self.async_qdrant_client.get_collection(collection_name=collection_name)
        return collection_info

    async def delete_collection(self, collection_name: str) -> None:
        """Deletes a collection.

        Arguments:
            collection_name: The name of the collection to delete.
        """
        await self.async_qdrant_client.delete_collection(collection_name=collection_name)

    async def update_collection(self, collection_name: str, **kwargs):
        await self.async_qdrant_client.update_collection(collection_name=collection_name, **kwargs)

    async def get_all_collections(
        self,
    ) -> list[str]:
        """Gets the list of collections.

        Returns: The list of collections.
        """
        collection_info = await self.async_qdrant_client.get_collections()
        return [collection.name for collection in collection_info.collections]

    async def does_collection_exist(self, collection_name: str) -> bool:
        """Checks if a collection exists.

        Arguments:
            collection_name: The name of the collection to check.

        Returns:
            bool: True if the collection exists; otherwise, False.
        """
        return await self.async_qdrant_client.collection_exists(collection_name=collection_name)
   
    async def get_collection_info(self, collection_name: str) -> types.CollectionInfo:
        return await self.async_qdrant_client.get_collection(collection_name=collection_name)

    async def add(
        self,
        collection_name: str,
        documents: Iterable[str],
        names: Iterable[str | None] | None = None,
        categories: Iterable[str | None] | None = None,
        kinds: Iterable[str | None] | None = None,
        created_datetimes: Iterable[datetime | None] | None= None,
        updated_datetimes: Iterable[datetime | None] | None = None,
        metadata: Iterable[dict[str, Any]] | None = None,
        ids: Iterable[ExtendedPointId] | None = None,
        batch_size: int = 32,
        parallel: int | None = None,
        **kwargs,
    ) -> list[str | int]:
        """
        Adds text documents into qdrant collection.
        If collection does not exist, it will be created with default parameters.
        Metadata in combination with documents will be added as payload.
        Documents will be embedded using the specified embedding model.

        If you want to use your own vectors, use `upsert` method instead.

        Args:
            collection_name (str):
                Name of the collection to add documents to.
            documents (Iterable[str]):
                List of documents to embed and add to the collection.
            names (Iterable[str | None]):
                Specify the corresponding name. It is part of the metadata.
                Default to None.
            categorys (Iterable[str | None] | None):
                Specify the corresponding category. It is part of the metadata.
                Default to None.
            kinds (Iterable[str | None] | None):
                Specify the corresponding kind. It is part of the metadata.
                Default to None.
            created_datetimes (Iterable[datetime | None]):
                The time of creation. If not specified, it will be generated automatically.
            updated_datetimes (Iterable[datetime | None] | None):
                The time of modification. If not specified, it will be generated automatically.
            metadata (Iterable[Dict[str, Any]] | None):
                List of other metadata dicts. Defaults to None.
            ids (Iterable[models.ExtendedPointId] | None):
                List of ids to assign to documents.
                If not specified, UUIDs will be generated. Defaults to None.
            batch_size (int | None):
                How many documents to embed and upload in single request. Defaults to 32.
            parallel (Optional[int] | None):
                How many parallel workers to use for embedding. Defaults to None.
                If number is specified, data-parallel process will be used.

        Raises:
            ImportError: If fastembed is not installed.

        Returns:
            List of IDs of added documents. If no ids provided, UUIDs will be randomly generated on client side.
        """
        _import_fastembed()
        current_utc_datetime = datetime.now(timezone.utc)
        time_now_rfc3339 = current_utc_datetime.isoformat()
        none_cycle = cycle([None])
        time_now_cycle = cycle([time_now_rfc3339])
        names_ = iter(names) if names is not None else none_cycle
        categories_ = iter(categories) if categories is not None else none_cycle
        kinds_ = iter(kinds) if kinds is not None else none_cycle
        created_datetimes_ = iter(created_datetimes) if created_datetimes is not None else time_now_cycle
        updated_datetimes_ = iter(updated_datetimes) if updated_datetimes is not None else time_now_cycle
        metadata_ = iter(metadata) if metadata is not None else cycle([{}])
        updated_metadata = (
            {
                "name": next(names_),
                "category": next(categories_),
                "kind": next(kinds_),
                "created_datatime": next(created_datetimes_),
                "updated_datetime": next(updated_datetimes_),
                **next(metadata_)
            } for _ in documents
        )
        return await self.async_qdrant_client.add(
            collection_name=collection_name,
            documents=documents,
            metadata=updated_metadata,
            ids=ids,
            batch_size=batch_size,
            parallel=parallel,
            **kwargs
        )

    async def query(
        self,
        collection_name: str,
        query_text: str,
        query_filter: Filter | None = None,
        limit: int = 10,
        **kwargs,
    ) -> list[QueryResponse]:
        """
        Search for documents in a collection.
        This method automatically embeds the query text using the specified embedding model.
        If you want to use your own query vector, use `search` method instead.

        Args:
            collection_name: Collection to search in
            query_text:
                Text to search for. This text will be embedded using the specified embedding model.
                And then used as a query vector.
            query_filter:
                Exclude vectors which doesn't fit given conditions.
                If `None` - search among all vectors
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            List[types.ScoredPoint]: List of scored points.

        """
        _import_fastembed()
        return await self.async_qdrant_client.query(
            collection_name=collection_name,
            query_text=query_text,
            query_filter=query_filter,
            limit=limit,
            **kwargs,
        )

    async def query_batch(
        self,
        collection_name: str,
        query_texts: list[str],
        query_filter: Filter | None = None,
        limit: int = 10,
        **kwargs,
    ) -> list[list[QueryResponse]]:
        """
        Search for documents in a collection with batched query.
        This method automatically embeds the query text using the specified embedding model.

        Args:
            collection_name: Collection to search in
            query_texts:
                A list of texts to search for. Each text will be embedded using the specified embedding model.
                And then used as a query vector for a separate search requests.
            query_filter:
                Exclude vectors which doesn't fit given conditions.
                If `None` - search among all vectors
                This filter will be applied to all search requests.
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            List[List[QueryResponse]]: List of lists of responses for each query text.

        """
        _import_fastembed()
        return await self.async_qdrant_client.query_batch(
            collection_name=collection_name,
            query_texts=query_texts,
            query_filter=query_filter,
            limit=limit,
            **kwargs,
        )

    async def delete(self, collection_name: str, filter: Filter) -> None:
        await self.async_qdrant_client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=filter)
        )

    async def scroll(
        self,
        collection_name: str,
        scroll_filter: types.Filter | None = None,
        limit: int = 10,
        with_payload: bool | Sequence[str] | types.PayloadSelector = True,
        with_vectors: bool | Sequence[str]= False,
        order_by: types.OrderBy | None = None,
    ) -> tuple[list[types.Record], types.PointId | None]:
        """Scroll over all (matching) points in the collection.

        This method provides a way to iterate over all stored points with some optional filtering condition.
        Scroll does not apply any similarity estimations, it will return points sorted by id in ascending order.

        Args:
            collection_name: Name of the collection
            scroll_filter: If provided - only returns points matching filtering conditions
            limit: How many points to return
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` (default) - Do not attach vector.
                - If List of string - include only specified fields
            order_by: Order the records by a payload key. If `None` - order by id

        Returns:
            A pair of (List of points) and (optional offset for the next scroll request).
            If next page offset is `None` - there is no more points in the collection to scroll.
        """
        return await self.async_qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            order_by=order_by,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )

    async def count(
        self,
        collection_name: str,
        count_filter: types.Filter | None = None,
        exact: bool = True
    ) -> int:
        """Count points in the collection.

        Count points in the collection matching the given filter.

        Args:
            collection_name: name of the collection to count points in
            count_filter: filtering conditions
            exact:
                If `True` - provide the exact count of points matching the filter.
                If `False` - provide the approximate count of points matching the filter. Works faster.
        Returns:
            Amount of points in the collection matching the filter.
        """
        result = await self.async_qdrant_client.count(
            collection_name=collection_name,
            count_filter=count_filter,
            exact=exact,
        )
        return result.count

    def metadata_filter(
        self,
        names: list[str] | None = None,
        categories: list[str] | None = None,
        kinds: list[str] | None = None,
        created_datetime_range: tuple[datetime | None, datetime | None] = (None, None,),
        updated_datetime_range: tuple[datetime | None, datetime | None] = (None, None,),
        document_texts: list[str] | None = None,
    ) -> Filter:
        
        name_condition = models.FieldCondition(
            key="name", match=models.MatchAny(any=names),
        ) if names else models.FieldCondition(
            key="name", match=models.MatchExcept(**{"except": []})
        )

        category_condition = models.FieldCondition(
            key="category", match=models.MatchAny(any=categories),
        ) if categories else models.FieldCondition(
            key="category", match=models.MatchExcept(**{"except": []})
        )

        kind_condition = models.FieldCondition(
            key="kind", match=models.MatchAny(any=kinds),
        ) if kinds else models.FieldCondition(
            key="kind", match=models.MatchExcept(**{"except": []})
        )

        created_datatime_range_condition = models.FieldCondition(
            key="created_datetime", range=models.DatetimeRange(
                gt=None,
                gte=created_datetime_range[0],
                lt=None,
                lte=created_datetime_range[1],
            )
        )

        updated_datatime_range_condition = models.FieldCondition(
            key="updated_datetime", range=models.DatetimeRange(
                gt=None,
                gte=updated_datetime_range[0],
                lt=None,
                lte=updated_datetime_range[1],
            )
        )

        document_text_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="document", match=models.MatchText(text=text),
                ) for text in document_texts
            ]
        ) if document_texts else models.Filter(
            must_not=[
                models.IsEmptyCondition(is_empty=models.PayloadField(key="document"))
            ]
        )

        filter = models.Filter(
            must=[
                name_condition,
                category_condition,
                kind_condition,
                created_datatime_range_condition,
                updated_datatime_range_condition,
                document_text_condition,
            ],
        )
        return filter
