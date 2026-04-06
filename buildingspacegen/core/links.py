"""Path loss and RF link models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# Minimal Graph class for networkx compatibility
class Graph:
    """Minimal directed graph implementation."""
    def __init__(self):
        self._edges = {}
        self._nodes = set()

    def add_node(self, node):
        self._nodes.add(node)

    def add_edge(self, u, v, **attrs):
        self.add_node(u)
        self.add_node(v)
        if u not in self._edges:
            self._edges[u] = {}
        self._edges[u][v] = attrs

    def edges(self, data=False):
        for u in self._edges:
            for v, attrs in self._edges[u].items():
                if data:
                    yield (u, v, attrs)
                else:
                    yield (u, v)

    def nodes(self):
        return self._nodes

# Alias for networkx compat
nx = None
try:
    import networkx as nx_real
    nx = nx_real
except ImportError:
    pass


@dataclass
class LinkResult:
    """RF link calculation result between two devices."""
    tx_device_id: str
    rx_device_id: str
    frequency_hz: float
    distance_m: float
    fspl_db: float  # Free space path loss
    wall_loss_db: float
    path_loss_db: float
    rx_power_dbm: float
    walls_crossed: int
    wall_details: list[dict] = field(default_factory=list)
    link_viable: bool = False
    link_margin_db: float = 0.0


class PathLossGraph:
    """Graph of RF links between devices."""

    def __init__(self):
        """Initialize empty path loss graph."""
        self._links: dict[tuple[str, str, float], LinkResult] = {}

    def add_link(self, link: LinkResult) -> None:
        """Add a link result."""
        key = (link.tx_device_id, link.rx_device_id, link.frequency_hz)
        self._links[key] = link

    def get_link(
        self, dev_a_id: str, dev_b_id: str, frequency_hz: float
    ) -> Optional[LinkResult]:
        """Get link from A to B at frequency."""
        key = (dev_a_id, dev_b_id, frequency_hz)
        return self._links.get(key)

    def get_viable_links(self, frequency_hz: float) -> list[LinkResult]:
        """Get all viable links at a frequency."""
        return [
            link
            for link in self._links.values()
            if link.frequency_hz == frequency_hz and link.link_viable
        ]

    def get_device_neighbors(
        self, device_id: str, frequency_hz: float, min_margin_db: float = 0
    ) -> list[str]:
        """Get neighbor devices with viable links."""
        neighbors = []
        for link in self._links.values():
            if (
                link.tx_device_id == device_id
                and link.frequency_hz == frequency_hz
                and link.link_viable
                and link.link_margin_db >= min_margin_db
            ):
                neighbors.append(link.rx_device_id)
        return neighbors

    def to_networkx(self, frequency_hz: float):
        """Convert viable links to networkx graph."""
        if nx is not None:
            g = nx.Graph()
        else:
            g = Graph()
        for link in self._links.values():
            if link.frequency_hz == frequency_hz and link.link_viable:
                g.add_edge(
                    link.tx_device_id,
                    link.rx_device_id,
                    weight=link.path_loss_db,
                    margin=link.link_margin_db,
                )
        return g

    @property
    def all_links(self) -> list[LinkResult]:
        """Get all links."""
        return list(self._links.values())
