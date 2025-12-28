from datetime import datetime
from typing import List

from pydantic import BaseModel


class ClusterCentroid(BaseModel):
    """
    Pydantic model for a cluster centroid stored in Weaviate.
    """

    cluster_id: int
    centroid_vector: List[float]
    cluster_size: int
    last_updated: datetime
