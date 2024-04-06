"""
This module provides the main functionality to perform a conversion.
You can use this module instead of using **main.py**.
"""
import pickle
import sys
import logging
import matplotlib.pyplot as plt

from crdesigner.config.osm_config import osm_config as config
from crdesigner.map_conversion.osm2cr.converter_modules.cr_operations import export
from crdesigner.map_conversion.osm2cr.converter_modules.osm_operations import osm_parser
from crdesigner.map_conversion.osm2cr.converter_modules.utility import plots
from crdesigner.map_conversion.osm2cr.converter_modules.graph_operations import (
    road_graph,
    intersection_merger,
    offsetter,
    segment_clusters,
    lane_linker,
    mapillary
)


def step_collection_1(file: str) -> road_graph.Graph:
    # create graph-object. Define nodes, edges, ...
    graph = osm_parser.create_graph(file)
    # if TRUE --> delete all elements graph not directly linked to the central node
    if config.MAKE_CONTIGUOUS:
        logging.info("making graph contiguously")
        graph.make_contiguous()
    logging.info("merging close intersections")
    # delete nodes which are very close to each other
    # replace these deleted nodes (and their edges) with one new node (with its new edges).
    intersection_merger.merge_close_intersections(graph)
    if isinstance(graph, road_graph.SublayeredGraph):
        intersection_merger.merge_close_intersections(graph.sublayer_graph)
        logging.info("merge close intersections again")
    # linking the different edges as (for- or backward)successors
    graph.link_edges()
    return graph


def step_collection_2(graph: road_graph.Graph) -> road_graph.Graph:
    logging.info("linking lanes")
    # node has several directed edges. Link those as incoming and outgoing (connect those to one instance) for each node.
    lane_linker.link_graph(graph)
    if isinstance(graph, road_graph.SublayeredGraph):
        lane_linker.link_graph(graph.sublayer_graph)
        logging.info("linking lanes again")
    logging.info("interpolating waypoints")
    # interpolate additional points for each edge.
    # interpolated waypoints for each edge get later used for cropping
    graph.interpolate()
    logging.info("offsetting roads")
    # lane-segment supposed to be straight. If not: do straightening via offset
    offsetter.offset_graph(graph)
    if isinstance(graph, road_graph.SublayeredGraph):
        offsetter.offset_graph(graph.sublayer_graph)

    logging.info("cropping roads at intersections")
    # of edges of one node to close to each other: cut edges to reduce overlapping in the region of common node
    edges_to_delete = graph.crop_waypoints_at_intersections(config.INTERSECTION_DISTANCE)
    #if config.DELETE_SHORT_EDGES:
    #    logging.info("deleting short edges")
    #    graph.delete_edges(edges_to_delete)

    if isinstance(graph, road_graph.SublayeredGraph):
        edges_to_delete = graph.sublayer_graph.crop_waypoints_at_intersections(config.INTERSECTION_DISTANCE_SUBLAYER)
        if config.DELETE_SHORT_EDGES:
            graph.sublayer_graph.delete_edges(edges_to_delete)
            logging.info("delete short lanes edges again")
    logging.info("applying traffic signs to edges and nodes")
    mapillary.add_mapillary_signs_to_graph(graph)
    graph.apply_traffic_signs()
    logging.info("applying traffic lights to edges")
    graph.apply_traffic_lights()
    logging.info("creating waypoints of lanes")
    graph.create_lane_waypoints()
    return graph


def step_collection_3(graph: road_graph.Graph) -> road_graph.Graph:
    logging.info("creating segments at intersections")
    graph.create_lane_link_segments()
    logging.info("clustering segments")
    segment_clusters.cluster_segments(graph)
    if isinstance(graph, road_graph.SublayeredGraph):
        segment_clusters.cluster_segments(graph.sublayer_graph)
    logging.info("changing to desired interpolation distance and creating borders of lanes")
    graph.create_lane_bounds(config.INTERPOLATION_DISTANCE_INTERNAL / config.INTERPOLATION_DISTANCE)
    if config.DELETE_INVALID_LANES:
        logging.info("deleting invalid lanes")
        graph.delete_invalid_lanes()  
    if isinstance(graph, road_graph.SublayeredGraph):
        if config.DELETE_INVALID_LANES:
            graph.sublayer_graph.delete_invalid_lanes()
    logging.info("adjust common bound points")
    graph.correct_start_end_points()
    logging.info("done converting")
    #print("graph-->lights", len(graph.traffic_lights))
    # print("graph-> nodes", len(graph.nodes))
    # print("graph ->edges", len(graph.edges))
    return graph


class GraphScenario:
    """
    Class that represents a road network
    data is saved by a graph structure (RoadGraph)

    """

    def __init__(self, file: str):
        """
        loads an OSM file and converts it to a graph

        :param file: OSM file to be loaded
        :type file: str
        """
        logging.info("reading File and creating graph")

        # extracting out of OSM-file nodes and create GraphNodes.
        # define graph-object. Assign nodes, edges, ...
        graph = step_collection_1(file)
        # further adjustments to the graph: cropping, deeper adding traffic signs and lights to the graph, ...
        graph = step_collection_2(graph)

        graph = step_collection_3(graph)

        self.graph: road_graph.Graph = graph

    def plot(self):
        """
        plots the graph and shows it

        :return: None
        """
        logging.info("plotting graph")
        _, ax = plt.subplots()
        ax.set_aspect("equal")
        plots.draw_graph(self.graph, ax)
        if isinstance(self.graph, road_graph.SublayeredGraph):
            plots.draw_graph(self.graph.sublayer_graph, ax)
        plots.show_plot()

    def save_as_cr(self, filename: str):
        """
        exports the road network to a CommonRoad scenario

        :param filename: file name for scenario generation tool
        :return: None
        """
        if filename is not None:
            export.export(self.graph, filename)
        else:
            export.export(self.graph)

    def save_to_file(self, filename: str):
        """
        Saves the road network to a file and stores it on disk

        :param filename: name of the file to save
        :type filename: str
        :return: None
        """
        sys.setrecursionlimit(10000)
        with open(filename, "wb") as handle:
            pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
        sys.setrecursionlimit(1000)


def load_from_file(filename: str) -> GraphScenario:
    """
    loads a road network from a file
    Warning! Do only load files you trust!

    :param filename: name of the file to load
    :type filename: str
    :return: the loaded road network
    :rtype: graph_scenario
    """
    with open(filename, "rb") as handle:
        graph_scenario = pickle.load(handle)
        return graph_scenario
