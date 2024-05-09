import re
from typing import TYPE_CHECKING, Iterable

from .qdrant_vector import _import_fastembed
from ._text_splitter_base import TextSplitterInterface


if TYPE_CHECKING:
    import numpy as np


class SemanticTextSplitter(TextSplitterInterface):
    def __init__(self, max_sentences: int, semantic: bool = True, semantic_threshold: float = 0.9):
        _import_fastembed()
        from fastembed import TextEmbedding
        self.embedding_model = TextEmbedding()
        self.max_sentences = max_sentences
        self.semantic = semantic
        self.semantic_threshold = semantic_threshold or 0.95
        if not 0 <= semantic_threshold <= 1:
            raise ValueError("'semantic_threshold' must be between 0 and 1.")

    def split(self, text: str) -> Iterable[str]:
        semantic_pieces = self.split_by_semantic(text)
        if self.semantic is True:
            return (chunk for piece in semantic_pieces for chunk in self.split_by_sentence(piece, self.max_sentences))
        else:
            return (chunk for chunk in self.split_by_sentence(text, self.max_sentences))

    def split_by_sentence(self, text: str, max_sentences: int) -> Iterable[str]:
        sentences = re.split(r'(?<=[。！？\.!?])\s*', text)
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

        for i in range(0, len(sentences), max_sentences):
            chunk = ''.join(sentences[i:i+max_sentences])
            yield chunk

    def _get_embeddings(self, texts: str | list[str]) -> Iterable[np.ndarray]:
        return self.embedding_model.embed(texts)

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate the cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude_vec1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude_vec2 = sum(b ** 2 for b in vec2) ** 0.5
        if magnitude_vec1 == 0 or magnitude_vec2 == 0:
            return 0
        else:
            return dot_product / (magnitude_vec1 * magnitude_vec2)
    
    def split_by_semantic(self, text: str) -> Iterable[str]:
        single_sentences = self.split_by_sentence(text, 1)
        sentences = [{'sentence': x, 'index': i} for i, x in enumerate(single_sentences)]
        
        embeddings = list(self._get_embeddings([x['combined_sentence'] for x in sentences]))
        for i, sentence in enumerate(sentences):
            sentence['combined_sentence_embedding'] = embeddings[i]
        distances, sentences = self._calculate_cosine_distances(sentences)
        
        breakpoint_distance_threshold = self._calculate_distance_threshold(distances, self.semantic_threshold)
        indices_above_thresh = [i for i, x in enumerate(distances) if x > breakpoint_distance_threshold]
        
        start_index = 0
        # Iterate through the breakpoints to slice the sentences
        for index in indices_above_thresh:
            # The end index is the current breakpoint
            end_index = index

            # Slice the sentence_dicts from the current start index to the end index
            group = sentences[start_index : end_index+1]
            combined_text = ' '.join([d['sentence'] for d in group])
            yield combined_text
            
            # Update the start index for the next group
            start_index = index + 1

        # The last group, if any sentences remain
        if start_index < len(sentences):
            combined_text = ' '.join([d['sentence'] for d in sentences[start_index:]])
            yield combined_text

    def _combine_sentences(self, sentences, buffer_size=1):
        for i in range(len(sentences)):

            combined_sentence = ''

            # Add sentences before the current one, based on the buffer size.
            for j in range(i - buffer_size, i):
                # Check if the index j is not negative (to avoid index out of range like on the first one)
                if j >= 0:
                    # Add the sentence at index j to the combined_sentence string
                    combined_sentence += sentences[j]['sentence'] + ' '

            # Add the current sentence
            combined_sentence += sentences[i]['sentence']

            # Add sentences after the current one, based on the buffer size
            for j in range(i + 1, i + 1 + buffer_size):
                # Check if the index j is within the range of the sentences list
                if j < len(sentences):
                    # Add the sentence at index j to the combined_sentence string
                    combined_sentence += ' ' + sentences[j]['sentence']

            # Store the combined sentence in the current sentence dict
            sentences[i]['combined_sentence'] = combined_sentence

        return sentences

    def _calculate_distance_threshold(self, distances: list[float], percentile_threshold: float) -> float:
        if not 0 <= percentile_threshold <= 1:
            raise ValueError("'percentile_threshold' must be between 0 and 1.")
        if not distances:
            raise ValueError("The list of distance must not be empty.")
        sorted_distances = sorted(distances)
        index = int(len(sorted_distances) * percentile_threshold)
        index = min(index, len(sorted_distances) - 1)
        return sorted_distances[index]

    def _calculate_cosine_distances(self, sentences):
        distances = []
        for i in range(len(sentences) - 1):
            embedding_current = sentences[i]['combined_sentence_embedding']
            embedding_next = sentences[i + 1]['combined_sentence_embedding']
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(embedding_current.tolist(), embedding_next.tolist())
            
            # Convert to cosine distance
            distance = 1 - similarity

            # Append cosine distance to the list
            distances.append(distance)

            # Store distance in the dictionary
            sentences[i]['distance_to_next'] = distance

        # Optionally handle the last sentence
        # sentences[-1]['distance_to_next'] = None  # or a default value

        return distances, sentences
