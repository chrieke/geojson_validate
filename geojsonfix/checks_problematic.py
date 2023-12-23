from shapely.geometry import Polygon, mapping


def check_holes(geom: Polygon) -> bool:
    has_holes = False
    try:
        geom.interiors[0]
        has_holes = True
    except IndexError:
        pass
    return has_holes


def check_self_intersection(geom: Polygon) -> bool:
    # TODO how to check selfintersection
    return not geom.is_valid


def check_excessive_coordinate_precision(geometry: dict) -> bool:
    # Check x coordinate of first 2 coordinate pairs in geometry
    # TODO: Correct?
    coords = geometry["coordinates"][0]
    return any([len(str(coord[0]).split(".")[1]) > 6 for coord in coords[:2]])


def check_more_than_2d_coordinates(geometry: dict, check_all_coordinates=False) -> bool:
    """
    By default checks only the first coordinate pair to speed things up.

    Args:
        geometry:
        check_all_coordinates:

    Returns:

    """
    # TODO: should check_all_coordinates be activated?
    coords = geometry["coordinates"][0]
    first_coord = coords[0]
    if len(first_coord) > 2:
        return True
    elif check_all_coordinates:
        for ring in coords:
            for coord in ring:
                if len(coord) > 2:
                    return True
    else:
        return False


def check_crosses_antimeridian(geom: Polygon) -> bool:
    pass
