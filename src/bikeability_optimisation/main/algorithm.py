"""
The core algorithm of the bikeability optimisation project.
"""
import osmnx as ox
from bikeability_optimisation.helper.algorithm_helper import *
from bikeability_optimisation.helper.logger_helper import *
from copy import deepcopy
from pathlib import Path


def core_algorithm(nkG, nkG_edited, edge_dict, trips_dict, nk2nx_nodes,
                   nk2nx_edges, street_cost, starttime, logpath, output_folder,
                   save, minmode, rev):
    """
    For a detailed explanation of the algorithm please look at the
    documentation on github.
    :param nkG: Graph.
    :type nkG: networkit graph
    :param nkG_edited: Graph that can be edited.
    :type nkG_edited: networkit graph
    :param edge_dict: Dictionary of edges of G. {edge: edge_info}
    :type edge_dict: dict of dicts
    :param trips_dict: Dictionary with al information about the trips.
    :type trips_dict: dict of dicts
    :param nk2nx_nodes: Dictionary that maps nk nodes to nx nodes.
    :type nk2nx_nodes: dict
    :param nk2nx_edges: Dictionary that maps nk edges to nx edges.
    :type nk2nx_edges: dict
    :param street_cost: Dictionary with construction cost of street types
    :type street_cost: dict
    :param starttime: Time the script started. For logging only.
    :type starttime: timestamp
    :param logpath: Location of the log file
    :type logpath: str
    :param output_folder: Folder where the output should be stored.
    :type output_folder: str
    :param save: Save name of the network
    :type save: str
    :param minmode: Which minmode should be chosen
    :type minmode: int
    :param rev: If true, builds up bike paths, not removes.
    :type rev: bool
    :return: data array
    :rtype: numpy array
    """
    # Create new sub folder for interim data
    int_out_folder = output_folder+'interim/'
    Path(int_out_folder).mkdir(parents=True, exist_ok=True)

    # Initial calculation
    print('Initial calculation started.')
    calc_trips(nkG, edge_dict, trips_dict)
    print('Initial calculation ended.')

    # Initialise lists
    total_cost = [0]
    bike_path_perc = [bike_path_percentage(edge_dict)]
    total_real_distance_traveled = [total_len_on_types(trips_dict, 'real')]
    total_felt_distance_traveled = [total_len_on_types(trips_dict, 'felt')]
    nbr_on_street = [nbr_of_trips_on_street(trips_dict)]
    len_saved = [0]
    edited_edges = []
    edited_edges_nx = []
    cc_n, cc_size = get_connected_bike_components(nkG_edited)
    nbr_of_cbc = [cc_n]
    gcbc_size = [max(cc_size.values(), default=0)]

    if rev:
        log_at = [0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6,
                  0.7, 0.8, 0.9, 1]
    else:
        log_at = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1,
                  0.05, 0.025, 0.01, 0]
    log_idx = 0

    while True:
        # Calculate minimal loaded unedited edge:
        min_loaded_edge = get_minimal_loaded_edge(edge_dict, trips_dict,
                                                  minmode=minmode, rev=rev)
        if min_loaded_edge == 'We are done!':
            print(min_loaded_edge)
            break
        edited_edges.append(min_loaded_edge)
        edited_edges_nx.append(get_nx_edge(min_loaded_edge, nk2nx_edges))
        nkG_edited.removeEdge(min_loaded_edge[0], min_loaded_edge[1])
        remove_isolated_nodes(nkG_edited)
        # Calculate len of all trips running over min loaded edge.
        len_before = get_len_of_trips_over_edge(min_loaded_edge, edge_dict,
                                                trips_dict)
        # Calculate cost of "adding" bike path
        total_cost.append(get_cost(min_loaded_edge, edge_dict, street_cost))
        # Edit minimal loaded edge and update edge_dict.
        edit_edge(nkG, edge_dict, min_loaded_edge)
        # Get all trips affected by editing the edge
        if not edge_dict[min_loaded_edge]['real bp']:
            if rev:
                trips_recalc = deepcopy(trips_dict)
            else:
                trips_recalc = {trip: trips_dict[trip] for trip
                                in edge_dict[min_loaded_edge]['trips']}
        else:
            trips_recalc = {}

        # Recalculate all affected trips and update their information.
        calc_trips(nkG, edge_dict, trips_recalc)
        trips_dict.update(trips_recalc)
        # Calculate length saved if not editing this edge.
        len_after = get_len_of_trips_over_edge(min_loaded_edge, edge_dict,
                                               trips_dict)
        len_saved.append(len_before - len_after)
        # Store all important data
        bike_path_perc.append(bike_path_percentage(edge_dict))
        total_real_distance_traveled.append(total_len_on_types(trips_dict,
                                                               'real'))
        total_felt_distance_traveled.append(total_len_on_types(trips_dict,
                                                               'felt'))
        nbr_on_street.append(nbr_of_trips_on_street(trips_dict))
        cc_n, cc_size = get_connected_bike_components(nkG_edited)
        nbr_of_cbc.append(cc_n)
        gcbc_size.append(max(cc_size.values(), default=0))

        # Logging
        next_log = log_at[log_idx]
        if (rev and bike_path_perc[-1] > next_log) ^ \
                (not rev and bike_path_perc[-1] < next_log):
            log_to_file(file=logpath, txt='Reached {0:3.2f} BLP'
                        .format(next_log), stamptime=time.localtime(),
                        start=starttime, end=time.time(), stamp=True,
                        difference=True)
            data = np.array([edited_edges, edited_edges_nx, total_cost,
                             bike_path_perc, total_real_distance_traveled,
                             total_felt_distance_traveled, nbr_on_street,
                             len_saved, nbr_of_cbc, gcbc_size])
            loc = int_out_folder+'{0:}_data_mode_{1:d}{2:}_{3:02d}.npy'\
                .format(save, rev, minmode, log_idx+1)
            mes = 'Saved at BLP {0:} as {1:}_data_mode_{2:d}{3:}_{4:02d}.npy'\
                .format(next_log, save, rev, minmode, log_idx+1)
            save_data(loc, data, logpath, mes)
            log_idx += 1

    # Save data of this run to data array
    data = np.array([edited_edges, edited_edges_nx, total_cost, bike_path_perc,
                     total_real_distance_traveled,
                     total_felt_distance_traveled, nbr_on_street, len_saved,
                     nbr_of_cbc, gcbc_size])
    return data


def run_simulation(place, save, input_folder, output_folder, log_folder,
                   real_bp, mode=(0, False)):
    """
    Prepares everything to run the core algorithm. All data will be saved to
    the given folders.
    :param place: Name of the place.
    :type place: str
    :param save: save name of everything associated with de place.
    :type save: str
    :param input_folder: Path to the input folder.
    :type input_folder: str
    :param output_folder: Path to the output folder.
    :type output_folder: str
    :param log_folder: Path to the log folder.
    :type log_folder: str
    :param mode: mode of the algorithm.
    :type mode: tuple
    :return: None
    """
    # Check if necessary folders exists, otherwise create.
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    Path(log_folder).mkdir(parents=True, exist_ok=True)

    # Start date and time for logging.
    sd = time.localtime()
    starttime = time.time()

    rev = mode[0]
    minmode = mode[1]

    logpath = log_folder + '{:s}_{:d}{:}.txt'.format(save, rev, minmode)
    # Initial Log
    log_to_file(logpath,
                'Started optimising {} with minmode {} and reversed {}'
                .format(place, minmode, rev),
                start=sd, stamp=False, difference=False)

    nxG = ox.load_graphml(filename='{}.graphml'.format(save),
                          folder=input_folder, node_type=int)
    nxG = nx.Graph(nxG.to_undirected())
    print('Simulating "{}" with {} nodes and {} edges.'
          .format(place, len(nxG.nodes), len(nxG.edges)))

    trip_nbrs_nx = np.load(input_folder+'{}_demand.npy'.format(save),
                           allow_pickle=True)[0]
    print('Number of trips: {}'.format(sum(trip_nbrs_nx.values())))

    # Exclude round trips
    trip_nbrs_nx = {trip_id: nbr_of_trips for trip_id, nbr_of_trips
                    in trip_nbrs_nx.items() if not trip_id[0] == trip_id[1]}
    print('Number of trips, round trips excluded: {}'.
          format(sum(trip_nbrs_nx.values())))

    # Convert networkx graph into network kit graph
    nkG = nk.nxadapter.nx2nk(nxG, weightAttr='length')
    nkG_edited = nk.nxadapter.nx2nk(nxG, weightAttr='length')
    nkG.removeSelfLoops()
    nkG_edited.removeSelfLoops()

    # Setup mapping dictionaries between nx and nk
    nx2nk_nodes = {list(nxG.nodes)[n]: n for n in range(len(list(nxG.nodes)))}
    nk2nx_nodes = {v: k for k, v in nx2nk_nodes.items()}
    nx2nk_edges = {(e[0], e[1]): (nx2nk_nodes[e[0]], nx2nk_nodes[e[1]])
                   for e in list(nxG.edges)}
    nk2nx_edges = {v: k for k, v in nx2nk_edges.items()}

    # Trips dict for the nk graph
    trip_nbrs_nk = {(nx2nk_nodes[k[0]], nx2nk_nodes[k[1]]): v
                    for k, v in trip_nbrs_nx.items()}

    # All street types in network
    street_types = get_all_street_types_cleaned(nxG)

    # Setup length on street type dict
    len_on_type = {t: 0 for t in street_types}
    len_on_type['bike path'] = 0

    # Set penalties for different street types
    penalties = {'primary': 7, 'secondary': 2.4, 'tertiary': 1.4,
                 'residential': 1.1}
    if rev:
        penalties = {k: 1 / v for k, v in penalties.items()}

    # Set cost for different street types
    street_cost = {'primary': 1, 'secondary': 1, 'tertiary': 1,
                   'residential': 1}

    # Setup trips and edge dict
    trips_dict = {t_id: {'nbr of trips': nbr_of_trips, 'nodes': [],
                         'edges': [], 'length real': 0, 'length felt': 0,
                         'real length on types': len_on_type,
                         'felt length on types': len_on_type,
                         'on street': False}
                  for t_id, nbr_of_trips in trip_nbrs_nk.items()}
    edge_dict = {edge: {'felt length': get_street_length(nxG, edge,
                                                         nk2nx_edges),
                        'real length': get_street_length(nxG, edge,
                                                         nk2nx_edges),
                        'street type': get_street_type_cleaned(nxG, edge,
                                                               nk2nx_edges),
                        'penalty': penalties[
                            get_street_type_cleaned(nxG, edge, nk2nx_edges)],
                        'speed limit': get_speed_limit(nxG, edge, nk2nx_edges),
                        'edited': False, 'bike path': not rev,
                        'real bp': False, 'load': 0, 'trips': []}
                 for edge in nkG.edges()}

    for edge in real_bp:
        nk_edge = nx2nk_edges[edge]
        edge_dict[nk_edge]['bike path'] = True
        edge_dict[nk_edge]['real bp'] = True

    if rev:
        for edge, edge_info in edge_dict.items():
            if not edge_info['real bp']:
                edge_info['felt length'] *= 1 / edge_info['penalty']
                nkG.setWeight(edge[0], edge[1], edge_info['felt length'])

    # Calculate data
    data = core_algorithm(nkG=nkG, nkG_edited=nkG_edited, edge_dict=edge_dict,
                          trips_dict=trips_dict, nk2nx_nodes=nk2nx_nodes,
                          nk2nx_edges=nk2nx_edges, street_cost=street_cost,
                          starttime=starttime, logpath=logpath,
                          output_folder=output_folder, save=save,
                          minmode=minmode, rev=rev)

    np.save(output_folder + '{:s}_data_mode_{:d}{:d}.npy'.format(save, rev,
                                                                 minmode),
            data)

    # Print computation time to console and write it to the log.
    log_to_file(logpath, 'Finished optimising {0:s}'
                .format(place), stamptime=time.localtime(), start=starttime,
                end=time.time(), stamp=True, difference=True)
    return 0
