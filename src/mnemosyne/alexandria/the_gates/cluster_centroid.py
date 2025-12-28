from datetime import datetime

from pydantic import BaseModel


class ClusterCentroid(BaseModel):
    """
    Pydantic model for a cluster centroid stored in Weaviate.
    """

    cluster_id: int
    centroid_vector: list[float]
    cluster_size: int
    last_updated: datetime
