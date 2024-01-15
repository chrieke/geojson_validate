from typing import List, Any, Union
import json
from json_source_map import calculate


class GeoJsonLint:
    """
    Validates if the GeoJSON conforms to the geojson json schema rules 2020-12
    (https://json-schema.org/draft/2020-12/release-notes)

    In comparison to simple comparison to the schema via jsonschema library, this adds
    error line positions and clearer handling.

    Inspired by https://github.com/mapbox/geojsonhint (paused Javascript library)
    Focuses on structural GEOJSON schema validation, not GeoJSON specification geometry rules.
    """

    GEOMETRY_TYPES = [
        "FeatureCollection",
        "Feature",
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
        "GeometryCollection",
    ]
    GEOJSON_TYPES = [
        "FeatureCollection",
        "Feature",
    ] + GEOMETRY_TYPES

    def __init__(self, check_crs: bool = False):
        self.check_crs = check_crs
        self.feature_idx = None
        self.line_map = None
        self.errors = {}

    def lint(self, geojson_data: Union[dict, Any]):
        if not isinstance(geojson_data, dict):
            self._add_error("Root of GeoJSON must be an object/dictionary", 0)
            return self.errors

        formatted_geojson_string = json.dumps(
            geojson_data, sort_keys=True, indent=2, separators=(",", ": ")
        )
        self.line_map = calculate(formatted_geojson_string)

        self._validate_geojson_root(geojson_data)

        return self.errors

    def _add_error(self, message: str, line: int):
        # self.errors.append({"message": message, "line": line or None})
        if message not in self.errors:
            self.errors[message] = {"lines": [line], "features": [self.feature_idx]}
        else:
            self.errors[message]["lines"].append(line)
            self.errors[message]["features"].append(self.feature_idx)

    def _get_line_number(self, path: str):
        entry = self.line_map.get(path)
        return entry.value_start.line + 1 if entry else None  # zero-indexed

    def _validate_geojson_root(self, obj: Union[dict, Any]):
        """Validate that the geojson object root directory conforms to the requirements."""
        root_path = ""
        if self._is_invalid_type_member(obj, self.GEOJSON_TYPES, root_path):
            return

        obj_type = obj.get("type")
        if obj_type == "FeatureCollection":
            self._validate_feature_collection(obj, root_path)
        elif obj_type == "Feature":
            self._validate_feature(obj, root_path)
        elif obj_type in self.GEOMETRY_TYPES:
            self._validate_geometry(obj, root_path)

    def _validate_feature_collection(
        self, feature_collection: Union[dict, Any], path: str
    ):
        """Validate that the featurecollection object conforms to the requirements."""
        self._is_invalid_type_member(
            feature_collection, ["FeatureCollection"], f"{path}/type"
        )

        if self.check_crs and "crs" in feature_collection:
            self._add_error(
                "The newest GeoJSON specification defines GeoJSON as always latitude/longitude, remove "
                "CRS (coordinate reference system) member",
                self._get_line_number(f"{path}/crs"),
            )

        if not self._is_invalid_property(
            feature_collection, "features", "array", f"{path}/features"
        ):
            for idx, feature in enumerate(feature_collection["features"]):
                self.feature_idx = idx
                if not isinstance(feature, dict):
                    self._add_error(
                        "Every feature must be a dictionary/object.",
                        self._get_line_number(f"{path}/features/{idx}"),
                    )
                else:
                    self._validate_feature(feature, f"{path}/features/{idx}")

    def _validate_feature(self, feature: Union[dict, Any], path: str):
        """Validate that the feature object conforms to the requirements."""
        self._is_invalid_type_member(feature, ["Feature"], f"{path}/type")
        if "id" in feature and not isinstance(feature["id"], (str, int)):
            self._add_error(
                'Feature "id" member must be a string or int number',
                self._get_line_number(f"{path}/id"),
            )
        self._is_invalid_property(feature, "properties", "object", f"{path}/properties")
        self._is_invalid_property(feature, "geometry", "object", f"{path}/geometry")
        geom = feature.get("geometry")
        if geom:
            self._validate_geometry(geom, f"{path}/geometry")

    def _validate_geometry(self, geometry: dict, path: str):
        """Validate that the geometry object conforms to the requirements."""
        if self._is_invalid_type_member(
            geometry, self.GEOMETRY_TYPES, f"{path}/type"
        ):  # TODO: path
            return

        obj_type = geometry.get("type")
        if obj_type == "GeometryCollection":
            if not self._is_invalid_property(geometry, "geometries", "array", path):
                for idx, geom in enumerate(geometry["geometries"]):
                    self._validate_geometry(geom, f"{path}/geometries/{idx}")
        elif not self._is_invalid_property(geometry, "coordinates", "array", path):
            if obj_type in ["Point"]:
                self._validate_position(geometry["coordinates"], f"{path}/coordinates")
            elif obj_type in ["LineString", "MultiPoint"]:
                self._validate_position_array(
                    geometry["coordinates"], 1, f"{path}/coordinates"
                )
            elif obj_type in ["Polygon", "MultiLineString"]:
                self._validate_position_array(
                    geometry["coordinates"], 2, f"{path}/coordinates"
                )
            elif obj_type in ["MultiPolygon"]:
                self._validate_position_array(
                    geometry["coordinates"], 3, f"{path}/coordinates"
                )

    def _is_invalid_type_member(
        self, obj: Union[dict, Any], allowed_types: List[str], path: str
    ):
        """
        Checks if an object type member conforms to the requirements.

        Args:
            obj: The object to check the property of
            allowed_types: List of the allowed types to check against.
            path: The line_map path pointing to the type property in question.
        """
        if not isinstance(obj, dict):
            return True
        obj_type = obj.get("type")
        if not obj_type:
            self._add_error(
                "Missing 'type' member", self._get_line_number(path.split("/type")[0])
            )
            return True
        elif obj_type not in allowed_types:
            self._add_error(
                f"Invalid 'type' member, is '{obj_type}', must be one of {allowed_types}",
                self._get_line_number(path),
            )
            return True
        return False

    def _is_invalid_property(
        self, obj: Union[dict, Any], name: str, type_str: str, path: str
    ):
        """
        Checks if an object property conforms to the requirements.

        Args:
            obj: The object to check the property of
            type_str: The expected type as a string, one of "array" or "object"
            name: The property name
            path: The line_map path pointing to the property in question.
        """
        if name not in obj:
            self._add_error(
                f'"{name}" member required',
                self._get_line_number(path.split("/" + name)[0]),
            )
            return True
        elif type_str == "array" and not isinstance(obj[name], list):
            self._add_error(
                f'"{name}" member must be an array, but is a {type(obj[name]).__name__} instead',
                self._get_line_number(path),
            )
            return True
        elif type_str == "object" and not isinstance(obj[name], dict):
            if name in ["geometry", "properties"] and obj[name] is None:
                return False
            self._add_error(
                f'"{name}" member must be an object/dictionary, but is a {type(obj[name]).__name__} instead',
                self._get_line_number(path),
            )
            return True
        return False

    def _validate_position(self, coords: Union[list, Any], path: str):
        """Validate that the single coordinate position conforms to the requirements."""
        if not isinstance(coords, list):
            return self._add_error(
                "Coordinate position must be an array",
                self._get_line_number(path),
            )
        if len(coords) < 2 or len(coords) > 3:
            self._add_error(
                "Coordinate position must have exactly 2 or 3 values",
                self._get_line_number(path),
            )
        if not all(isinstance(coord, (int, float)) for coord in coords):
            self._add_error(
                "Each element in a coordinate position must be a number",
                self._get_line_number(path),
            )

    def _validate_position_array(self, coords: Union[list, Any], depth: int, path: str):
        """Validate that the array of multiple coordinate positions conforms to the requirements."""
        if depth == 0:
            return self._validate_position(coords, path)
        if not isinstance(coords, list):
            return self._add_error(
                "Coordinates must be an array",
                self._get_line_number(path),
            )
        for p in coords:
            self._validate_position_array(p, depth - 1, path)
