
if(0):
    import osmnx as ox
    import networkx as nx
    import matplotlib.pyplot as plt

    ox.config(use_cache=False,
              log_console=True,
              useful_tags_way=ox.settings.useful_tags_way + ['railway'])

    G = ox.graph_from_place('Leipzig, Germany',#'Geneva, Switzerland', #Hannover, Germany
                            retain_all=False, truncate_by_edge=True, simplify=True,
                            custom_filter='["railway"~"tram|rail"]')
    len(G) #1776
    #print(G)

    # Plot the graph
    ox.plot_graph(G, node_size=0, edge_color='b', bgcolor='w')

    # Show the plot
    plt.show()


#####################


