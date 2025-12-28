from dataclasses import dataclass


@dataclass
class ChunkRepresentation:
    """
    Represents a chunk of text for use in cluster analysis.
    """

    chunk_id: str
    source_file: str
    text: str
    heading_path: str
    distance_from_centroid: float
    chunk_index: int
