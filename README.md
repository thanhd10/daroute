# **About this repository**

This repository contains the code used for the paper **"DaRoute: Inferring trajectories from zero-permission smartphone sensors"**
published at the "International Conference on Privacy, Security and Trust (PST2021)".
The paper can be downloaded at ResearchGate [here](https://www.researchgate.net/publication/356253751_DaRoute_Inferring_trajectories_from_zero-permission_smartphone_sensors).

*Note: The experiments in the paper were conducted by voluntary participants during their everyday life (i.e., routes reveal sensitive locations and driving patterns). 
Therefore, the dataset cannot be provided to respect the privacy of the drivers. Only a selected set of routes collected by the authors themselves can be provided.*

# **Setup the repository**

1. Clone the repository
2. Create following directory within the repo: *daroute/data/*
   - In this directory, street networks will be stored
   - This directory can also be used to place osm dumps, sensor files etc.
3. Repo was written and tested in Python 3.8. Therefore, as a recommendation, create a virtual environment in Python 3.8 and install the requirements defined in *requirements.txt*


# **Preparing the data**

Sensor readings of a trip were collected by an Android app that locally preprocessed the sensor data.
Preprocessing steps like sensor fusion of accelerometer and gyroscope data, averaging to 25 Hz, removing anomalies, or smartphone-to-vehicle alignment were included.

Each provided test route contains the following in a directory whose name starts with **"Route_"**:
1. *Leaflet_GPS.html*: The visualization of the route with GPS coordinates and mplleaflet to see the ground truth.
2. *Route_Sensor.json*: The preprocessed sensor data in the format of the DaRoute project.
                        Make sure that own sensor readings are in the same format and contain a) readings from the accelerometer across three axes, 
                        b) readings from the gyroscope across three axes, c) driving speed values, and d) a timeset in milliseconds.
3. *Start_Heading.txt*: A stable initial heading of the vehicle at the beginning of a trip.
4. *OSM_Nodes.txt*: A sequence of node ids from OpenStreetMap, where each turn of a route took place.
                    Collecting these was a manual work of checking route candidates and querying nearby turns from the turns_df based on GPS coordinates.

As already mentioned, not all routes were provided, as they contain sensitive information of voluntary participants.
Instead, a selected set of routes are provided in this repository that were collected by the authors themselves for evaluation purposes.
These test routes can be found under the directory *"data/regensburg"*. 
Additionally, an OSM dump for the smallest testing area of Regensburg (used in the paper) is provided under *"data/osm_export_12_04_21"*.
On request, we can provide the larger testing areas. 
They are not included in this repository due to their size.

# **Run the attack**

1. Run *attack_framework/create_street_network.py*
   - set variable OSM_FILE (reference to the file path of the osm dump) 
   - set variable TARGET_LOCATION (describing name for the location)
2. Run *attack_framework/infer_trajectory.py*
   - set variable JSON_FILE_PATH to the sensor readings of a driven route
   - set variable INITIAL_HEADING to the initial heading measured within a vehicle (can also be a stable magnetometer reading at the beginning of a driven route)
   - set variable TARGET_LOCATION to the TARGET_LOCATION defined in the previous step

Alternatively, run all tests with *test/test_routes.py* to test the provided test routes.
Results can then be found under *test/logs* and *test/results*.
In case you want to test your own data prepared in the above described format, and adjust the *test/settings.py*.
Make sure to create a street network before running the script *test/test_routes.py*.

# **Reproducing the experiments with data provided by Narain et al. (2016)**

While we cannot make the dataset collected in Regensburg available, the experiment results with the data provided by Narain et al. (2016) can be reproduced.
For this purpose, please request the authors Narain et al. (2016) for access to their code/dataset.


### In the following, a step-by-step guide is described to reproduce the experiment results of the DaRoute attack with the data provided by Narain et al. (2016):

1. Run *attack_framework/create_street_network.py*
   - set variable OSM_FILE (reference to the file path of the osm dump) 
   - set variable TARGET_LOCATION (describing name for the location)
2. Adjust *narain_attack/settings.py*
   - set variable TARGET_LOCATION to the TARGET_LOCATION defined in the previous step
   - set variable AREA to the name of the directory, were the raw data of Narain et al. (2016) is located in (no absolute path to the directory)
   - set variable SAMPLES_DIRECTORY to the absolute path of the raw data of Narain et al. (2016)
3. Run *narain_attack/sensor_data_processing/process.py*
   - Preprocessing of the raw data of Narain et al. (2016), e.g., smartphone-to-vehicle-alignment
4. Run *narain_attack/test/test_narain_data.py*
   - Results of the finished run can be found under *narain_attack/test/results*
   - Logs and intermediary results can be found under *narain_attack/test/logs*
