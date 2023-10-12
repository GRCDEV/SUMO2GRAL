from buildings.buildings_processor import BuildingProcessor as Buildings
from weather.weather_processor import WeatherDataProcessor as Weather
from line_emission_sources.highway_data_processor import HighwayDataProcessor as Highways
from maps.maps_processor import MapGenerator as Maps
from gral.gral_files_generator import GRAL
import osmnx as ox
import sumolib as sumo
import os


def create_shapefile(geo_df, coordinate_system, directory, filename):
    """
    Creates a shapefile from a GeoDataFrame.

    Parameters:
    geo_df (GeoDataFrame): The GeoDataFrame to be converted to a shapefile.
    coordinate_system (str): The coordinate reference system (CRS) of the GeoDataFrame, specified as an EPSG code.
    directory (str): The directory where the shapefile will be saved.
    filename (str): The name of the output shapefile.

    Returns:
    None
    """
    print("Creating shapefile...")
    try:
        # Reproject the GeoDataFrame to the specified coordinate system
        geo_df_reprojected = ox.projection.project_gdf(
            geo_df, to_crs=coordinate_system, to_latlong=False)

        # Define the coordinate reference system (CRS) i.e.: EPSG:4326
        geo_df_reprojected.crs = coordinate_system

        # Optionally, save the GeoDataFrame to a file
        geo_df_reprojected.to_file(
            f'{directory}/{filename}', driver='ESRI Shapefile')
    except Exception as e:
        print(f"Failed to create shapefile: {e}")


def main(args):
    try:
        # Define location dictionary from args
        location = {
            "north": args.north,
            "south": args.south,
            "east": args.east,
            "west": args.west
        }

        # Create objects for each module
        buildings_module = Buildings(location)
        weather_module = Weather(args.base_directory)
        highways_module = Highways(location)
        maps_module = Maps(args.base_directory)
        gral_module = GRAL(args.base_directory, args.met_file,
                           args.buildings_shapefile_filename, args.highways_shapefile_filename)

        # Process based on the specified argument
        if args.process in ['all', 'buildings']:
            buildings_gdf = buildings_module.process_buildings()
            create_shapefile(
                buildings_gdf,
                f"EPSG:{args.epsg}",
                args.base_directory,
                args.buildings_shapefile_filename
            )

        if args.process in ['all', 'weather']:
            weather_df, met_file_df = weather_module.process_weather_data(
                args.input_weather_file)
            weather_module.create_met_file(met_file_df)
            weather_module.write_to_files(
                weather_df, f'{args.output_weather_file}.csv')
            weather_module.write_to_files(
                met_file_df, f'{args.output_weather_file}.met')
            if not args.weather_day is None:
                day_met_file_df = met_file_df[met_file_df['fecha']
                                              == args.weather_day]
                weather_module.write_to_files(
                    day_met_file_df, f'{args.output_weather_file}_{args.weather_day}.met')
                if not args.weather_hour is None:
                    hour_met_file_df = day_met_file_df[(
                        day_met_file_df['hora'] == args.weather_hour)]
                    weather_module.write_to_files(
                        hour_met_file_df, f'{args.output_weather_file}_{args.weather_day}_{args.weather_hour}.met')

        if args.process in ['all', 'highway']:

            # Read the SUMO network file
            net_file = sumo.net.readNet(f'{args.net_file}')

            highway_gdf = highways_module.process_highway_data(net_file)

            # Read the SUMO emissions file
            sumo_emissions_df = highways_module.process_sumo_edges_emissions_file(
                args.emissions_file, net_file, highway_gdf['osmid'].tolist())

            # Combine the sumo emissions and highway data
            highway_emissions_gdf = highways_module.combine_sumo_emissions_and_highway_data(
                sumo_emissions_df, highway_gdf)

            create_shapefile(highway_emissions_gdf,
                             f"EPSG:{args.epsg}", args.base_directory, args.highways_shapefile_filename)

        if args.process in ['all', 'map']:
            # Convert the coordinates to EPSG
            west_point_epsg_new_x, north_point_epsg_new_y = maps_module.convert_coordinates(
                location["west"], location["north"], 4326, args.epsg)
            east_point_epsg_new_x, south_point_epsg_new_y = maps_module.convert_coordinates(
                location["east"], location["south"], 4326, args.epsg)

            # Dictionary with the location coordinates in EPSG:3857
            location_epsg_new = {"north": north_point_epsg_new_y, "south": south_point_epsg_new_y,
                                 "east": east_point_epsg_new_x, "west": west_point_epsg_new_x}
            maps_module.create_georeferenced_map(
                location_epsg_new,
                args.epsg,
                args.map_filename
            )
        if args.process in ['gral']:
            # Generate the files for GRAL executable
            # Convert the coordinates to EPSG
            west_point_epsg_new_x, north_point_epsg_new_y = maps_module.convert_coordinates(
                location["west"], location["north"], 4326, args.epsg)
            east_point_epsg_new_x, south_point_epsg_new_y = maps_module.convert_coordinates(
                location["east"], location["south"], 4326, args.epsg)

            # Dictionary with the location coordinates in EPSG:3857
            location_epsg_new = {"north": north_point_epsg_new_y, "south": south_point_epsg_new_y,
                                 "east": east_point_epsg_new_x, "west": west_point_epsg_new_x}

            pollutant = "NOx"
            # Define horizontal layers to simulate in meters
            horizontal_layers = [3,6,9,12,15]
            # Create the GREB file
            gral_module.create_greb_file(bbox=location_epsg_new, horizontal_slices=len(horizontal_layers))
            # Create the in.dat file
            mean_latitude = (location["north"] + location["south"]) / 2
            gral_module.create_in_dat_file(particles_ps=500, dispertion_time=3600, latitude=mean_latitude, horizontal_slices=horizontal_layers)
            # Create the meteogpt.all file
            gral_module.create_meteogpt_file()
            # Create the other requiered files
            gral_module.create_other_txt_requiered_files(pollutant=pollutant, n_cores=12)
            # Create the buildings file
            gral_module.create_buildings_file()
            # Create the line emission sources file
            gral_module.create_line_emissions_file(pollutant=pollutant)
            # Create the other optional files
            gral_module.create_other_optional_files()
            # Run the GRAL executable
            # os.system(f'{args.gral_exe}')
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    print("Please run the CLI.py script to use this program.")
