# **About this repository**

This repository contains the code used for the paper **"DaRoute: Inferring trajectories from zero-permission smartphone sensors"**
published at the "International Conference on Privacy, Security and Trust (PST2021)".
The paper can be downloaded at ResearchGate [here](https://www.researchgate.net/publication/356253751_DaRoute_Inferring_trajectories_from_zero-permission_smartphone_sensors).

*Note: The experiments in the paper were conducted by voluntary participants during their everyday life (i.e., routes reveal sensitive locations and driving patterns). 
Therefore, the dataset cannot be provided to respect the privacy of the drivers. Only a selected set of routes collected by the authors themselves can be provided.*

# **Reproducing the experiments with data provided by Narain et al. (2016)**

While we cannot make the dataset collected in Regensburg available, the experiment results with the data provided by Narain et al. (2016) can be reproduced.
For this purpose, please request the authors Narain et al. (2016) for access to their code/dataset.

### In the following, a step-by-step guide is described to reproduce the experiment results of the DaRoute attack with the data provided by Narain et al. (2016):

1. Clone the repository
2. Create following directory within the repo: *daroute/data/*
   - In this directory, street networks will be stored
   - This directory can also be used to place osm dumps, sensor files etc.
3. Repo was written and tested in Python 3.8. Therefore, as a recommendation, create a virtual environment in Python 3.8 and install the requirements defined in requirements.txt
4. Run attack_framework/create_*street_network.py*
   - set variable OSM_FILE (reference to the file path of the osm dump) 
   - set variable TARGET_LOCATION (describing name for the location)
5. Adjust *narain_attack/settings.py*
   - set variable TARGET_LOCATION to the TARGET_LOCATION defined in the previous step
   - set variable AREA to the name of the directory, were the raw data of Narain et al. (2016) is located in (no absolute path to the directory)
   - set variable SAMPLES_DIRECTORY to the absolute path of the raw data of Narain et al. (2016)
6. Run *narain_attack/sensor_data_processing/process.py*
   - Preprocessing of the raw data of Narain et al. (2016), e.g., smartphone-to-vehicle-alignment
7. Run *narain_attack/test/test_narain_data.py*
   - Results of the finished run can be found under *narain_attack/test/results*
   - Logs and intermediary results can be found under *narain_attack/test/logs*
