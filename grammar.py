from typing import Sized

from productions import *
from utils import *


class Grammar:
    """
    A grammar is a collection of productions that can be applied on a graph.
    """
    def __init__(self, productions: Iterable[Production]):
        self._productions: Iterable[Production] = productions

    def apply(self, target_graph: Graph, max_steps: int = 0) -> Iterable[Graph]:
        """
        Apply the productions of the grammar to a target graph and return a derivation
        sequence of the result graph.

        :param target_graph: The graph to which the productions will be applied.
        :param max_steps: The maximum number of productions to be applied. If 0
        then there is no limit, execution will only stop if
        :return: The sequence of graphs that results from applying the grammar to the target
        graph.
        """
        step_count = 0
        result_graphs = []
        new_host_graph = target_graph
        while True:
            production, matches = self._find_matching_production(new_host_graph)
            if production is None:
                break
            match = self._select_match(matches)
            matching_subgraph, matching_mapping = match
            new_host_graph = production.apply(new_host_graph, matching_mapping)
            result_graphs.append(new_host_graph)
            step_count += 1
            if 0 < max_steps < step_count:
                break
        return result_graphs

    def _find_matching_production(self, target_graph: Graph):
        """
        Find a single production that has at least one match against the target
        Graph.

        This function will randomly search the list of productions for a
        matching production.

        :param target_graph: The target graph to find a matching production against.
        :return: One matching production along with all the possible matching
        subgraphs of the target graph. If no match is found returns (None,[]).
        :rtype: Tupel[Production|None, List[Graph]]
        """
        result = (None, [])
        for production in randomly(self._productions):
            matching_subgraphs = production.match(target_graph)
            if len(matching_subgraphs) == 0:
                continue
            else:
                result = (production, matching_subgraphs)
                break
        return result

    @staticmethod
    def _select_match(matches: Sized and Iterable[Graph]):
        """
        Select a singe match out of a list of possible matches.

        :param matches: The list of matches from which to select one.
        :return: The selected match
        :rtype: Graph
        """
        i = random.randint(0, len(matches) - 1)
        return matches[i]
