import argparse
import os
import sys
import json
import pandas as pd
import boto3
from multiprocessing.pool import Pool
from h5coro import h5coro, s3driver, logger

# ################################################
# Command Line Arguments
# ################################################

parser = argparse.ArgumentParser(description="""ATL24""")
parser.add_argument('--summary_file',   type=str,   default="granule_collection.csv")
parser.add_argument('--url',            type=str,   default="s3://sliderule-public")
parser.add_argument('--concurrency',    type=int,   default=5)
parser.add_argument('--granule',        type=str,   default=None)
parser.add_argument("--loglvl" ,        type=str,   default="CRITICAL")
parser.add_argument("--cores",          type=int,   default=os.cpu_count())
args,_ = parser.parse_known_args()

# ################################################
# Constants
# ################################################

STATS = [
    ('granule',''),
    ('size',''),
    ('total_photons',''),
    ('sea_surface_photons',''),
    ('subaqueous_photons',''),
    ('bathy_photons',''),
    ('bathy_strong_photons',''),
    ('bathy_linear_coverage','.3f'),
    ('bathy_mean_depth','.3f'),
    ('bathy_min_depth','.3f'),
    ('bathy_max_depth','.3f'),
    ('bathy_std_depth','.3f'),
    ('sea_surface_std','.3f'),
    ('region',''),
    ('ascending',''),
    ('season',''),
    ('bathy_night_photons',''),
    ('bathy_gt1_photons',''),
    ('bathy_gt2_photons',''),
    ('bathy_gt3_photons',''),
    ('bathy_spot1_photons',''),
    ('bathy_spot2_photons',''),
    ('bathy_spot3_photons',''),
    ('bathy_spot4_photons',''),
    ('bathy_spot5_photons',''),
    ('bathy_spot6_photons',''),
    ('bathy_lat80S',''),
    ('bathy_lat70S',''),
    ('bathy_lat60S',''),
    ('bathy_lat50S',''),
    ('bathy_lat40S',''),
    ('bathy_lat30S',''),
    ('bathy_lat20S',''),
    ('bathy_lat10S',''),
    ('bathy_lat00S',''),
    ('bathy_lat10N',''),
    ('bathy_lat20N',''),
    ('bathy_lat30N',''),
    ('bathy_lat40N',''),
    ('bathy_lat50N',''),
    ('bathy_lat60N',''),
    ('bathy_lat70N',''),
    ('bathy_lat80N',''),
    ('bathy_high_night_photons',''),
    ('bathy_high_gt1_photons',''),
    ('bathy_high_gt2_photons',''),
    ('bathy_high_gt3_photons',''),
    ('bathy_high_spot1_photons',''),
    ('bathy_high_spot2_photons',''),
    ('bathy_high_spot3_photons',''),
    ('bathy_high_spot4_photons',''),
    ('bathy_high_spot5_photons',''),
    ('bathy_high_spot6_photons',''),
    ('bathy_high_lat80S',''),
    ('bathy_high_lat70S',''),
    ('bathy_high_lat60S',''),
    ('bathy_high_lat50S',''),
    ('bathy_high_lat40S',''),
    ('bathy_high_lat30S',''),
    ('bathy_high_lat20S',''),
    ('bathy_high_lat10S',''),
    ('bathy_high_lat00S',''),
    ('bathy_high_lat10N',''),
    ('bathy_high_lat20N',''),
    ('bathy_high_lat30N',''),
    ('bathy_high_lat40N',''),
    ('bathy_high_lat50N',''),
    ('bathy_high_lat60N',''),
    ('bathy_high_lat70N',''),
    ('bathy_high_lat80N',''),
]

VERSIONS = {
    "sliderule_version":    ("v4.9.3", "v4.9.4"),
    "openoceanspp_version": "3c474b8",
    "coastnet_version":     "5cc4b1b-dirty",
    "qtrees_version":       "35833ce-dirty",
    "cshelph_version":      "f1bbb00",
    "medianfilter_version": "4d0b946",
    "ensemble_version":     "6eabb00",
    "coastnet_model":       "coastnet_model-20241111.json",
    "qtrees_model":         "qtrees_model-20241105.json",
    "ensemble_model":       "/data/ensemble_model-20250201.json",
    "nsidc_version":        "001_01"
}

VARIABLES = [
    "lat_ph",
    "ortho_h",
    "night_flag",
    "low_confidence_flag",
    "class_ph"
]

BEAMS = [
    "gt1l",
    "gt1r",
    "gt2l",
    "gt2r",
    "gt3l",
    "gt3r"
]

BEAM_TO_SPOT = { # [SC_ORIENT][BEAM]
    0: { # SC_BACKWARD
        'gt1l': 1,
        'gt1r': 2,
        'gt2l': 3,
        'gt2r': 4,
        'gt3l': 5,
        'gt3r': 6
    },
    1: { # SC_FOWARD
        'gt1l': 6,
        'gt1r': 5,
        'gt2l': 4,
        'gt2r': 3,
        'gt3l': 2,
        'gt3r': 1
    }
}

REGION_TO_ASCENDING = {
    1: 1,
    2: 1,
    3: 1,
    4: 2,
    5: 0,
    6: 0,
    7: 0,
    8: 0,
    9: 0,
    10: 0,
    11: 2,
    12: 1,
    13: 1,
    14: 1,
}

MONTH_TO_SEASON = { #[is_north][month] --> 0: winter, 1: spring, 2: summer, 3: fall
    True: {
        1: 0,
        2: 0,
        3: 0,
        4: 1,
        5: 1,
        6: 1,
        7: 2,
        8: 2,
        9: 2,
        10: 3,
        11: 3,
        12: 3
    },
    False: {
        1: 2,
        2: 2,
        3: 2,
        4: 3,
        5: 3,
        6: 3,
        7: 0,
        8: 0,
        9: 0,
        10: 1,
        11: 1,
        12: 1
    }
}

# ################################################
# Initialize
# ################################################

logger.config(args.loglvl)
credentials = {"role": True, "profile":"sliderule"}
processed_granules = {} # [name]: True"
granules = [] # (name, size)
iso_xmls = {} # [name]: True

# ################################################
# Open Summary File
# ################################################

# get existing granules
if os.path.exists(args.summary_file):
    summary_df = pd.read_csv(args.summary_file)
    for granule in summary_df["granule"]:
        processed_granules[granule] = True
    summary_file = open(args.summary_file, "a")
else:
    summary_file = open(args.summary_file, "w")
    csv_header = [entry[0] for entry in STATS]
    summary_file.write(','.join(csv_header) + "\n")

# report number of existing granules
print(f'Processed granules: {len(processed_granules)}')

# ################################################
# List H5 Granules
# ################################################

if args.granule == None:
    # initialize s3 client
    s3 = boto3.client('s3')

    # get bucket and subfolder from url
    path = args.url.split("s3://")[-1]
    bucket = path.split("/")[0]
    subfolder = '/'.join(path.split("/")[1:])

    # read granules
    num_granules = 0
    num_empty_granules = 0
    is_truncated = True
    continuation_token = None
    while is_truncated:
        # make request
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=subfolder, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=subfolder)
        # display status
        print("#", end='')
        sys.stdout.flush()
        # parse contents
        if 'Contents' in response:
            for obj in response['Contents']:
                granule = obj['Key'].split("/")[-1]
                if granule.startswith("ATL24"):
                    if granule.endswith(VERSIONS["nsidc_version"] + ".h5"):
                        num_granules += 1
                        if granule not in processed_granules:
                            granules.append((granule, obj["Size"]))
                    elif granule.endswith(VERSIONS["nsidc_version"] + ".h5.empty"):
                        num_empty_granules += 1
                    elif granule.endswith(VERSIONS["nsidc_version"] + ".iso.xml"):
                        iso_xmls[granule.replace(".iso.xml", ".h5")] = True
        # check if more data is available
        is_truncated = response['IsTruncated']
        continuation_token = response.get('NextContinuationToken')
    print("") # new line
else:
    # for testing only
    num_granules = 1
    num_empty_granules = 0
    granules = [(args.granule, 0)]
    iso_xmls[args.granule] = True

# report new granules
print(f'Valid granules: {num_granules}')
print(f'Empty granules: {num_empty_granules}')
print(f'New granules to process: {len(granules)}')

# ################################################
# Helper Functions
# ################################################

def get_counts(df, column, value):
    value_counts = df[column].value_counts()
    if value in value_counts:
        return value_counts[value]
    else:
        return 0

def get_counts_series(s, value):
    value_counts = s.value_counts()
    if value in value_counts:
        return value_counts[value]
    else:
        return 0

def get_bathy_stats(df, prefix):
    lat_bins = (df["lat_ph"] / 10).astype(int)
    return {
        f'{prefix}_night_photons': get_counts(df, "night_flag", 1),
        f'{prefix}_gt1_photons': get_counts(df, "beam", "gt1l") + get_counts(df, "beam", "gt1r"),
        f'{prefix}_gt2_photons': get_counts(df, "beam", "gt2l") + get_counts(df, "beam", "gt2r"),
        f'{prefix}_gt3_photons': get_counts(df, "beam", "gt3l") + get_counts(df, "beam", "gt3r"),
        f'{prefix}_spot1_photons': get_counts(df, "spot", 1),
        f'{prefix}_spot2_photons': get_counts(df, "spot", 2),
        f'{prefix}_spot3_photons': get_counts(df, "spot", 3),
        f'{prefix}_spot4_photons': get_counts(df, "spot", 4),
        f'{prefix}_spot5_photons': get_counts(df, "spot", 5),
        f'{prefix}_spot6_photons': get_counts(df, "spot", 6),
        f'{prefix}_lat80S': get_counts_series(lat_bins, -8),
        f'{prefix}_lat70S': get_counts_series(lat_bins, -7),
        f'{prefix}_lat60S': get_counts_series(lat_bins, -6),
        f'{prefix}_lat50S': get_counts_series(lat_bins, -5),
        f'{prefix}_lat40S': get_counts_series(lat_bins, -4),
        f'{prefix}_lat30S': get_counts_series(lat_bins, -3),
        f'{prefix}_lat20S': get_counts_series(lat_bins, -2),
        f'{prefix}_lat10S': get_counts_series(lat_bins, -1),
        f'{prefix}_lat00S': get_counts_series(lat_bins, 0),
        f'{prefix}_lat10N': get_counts_series(lat_bins, 1),
        f'{prefix}_lat20N': get_counts_series(lat_bins, 2),
        f'{prefix}_lat30N': get_counts_series(lat_bins, 3),
        f'{prefix}_lat40N': get_counts_series(lat_bins, 4),
        f'{prefix}_lat50N': get_counts_series(lat_bins, 5),
        f'{prefix}_lat60N': get_counts_series(lat_bins, 6),
        f'{prefix}_lat70N': get_counts_series(lat_bins, 7),
        f'{prefix}_lat80N': get_counts_series(lat_bins, 8)
    }

# ################################################
# Append Stats for Each Granule
# ################################################

def stat_worker(arg):

    # initialize arguments
    granule, size = arg
    path = args.url.split("s3://")[-1] + "/" + granule

    try:
        # open granule
        h5obj = h5coro.H5Coro(path, s3driver.S3Driver, errorChecking=True, verbose=False, credentials=credentials, multiProcess=False)

        # read datasets
        datasets = [f'{beam}/{var}' for beam in BEAMS for var in VARIABLES] + ['metadata/sliderule', 'metadata/stats', 'orbit_info/sc_orient']
        promise = h5obj.readDatasets(datasets, block=True, enableAttributes=False)

        # pull out metadata
        sliderule = json.loads(promise["metadata/sliderule"])
        stats = json.loads(promise["metadata/stats"])

        # check versions
        if not (sliderule["sliderule_version"] in VERSIONS["sliderule_version"] and \
        sliderule["coastnet_version"] == VERSIONS["coastnet_version"] and \
        sliderule["qtrees_version"] == VERSIONS["qtrees_version"] and \
        sliderule["openoceanspp_version"] == VERSIONS["openoceanspp_version"] and \
        sliderule["ensemble"]["version"] == VERSIONS["ensemble_version"] and \
        sliderule["coastnet"]["model"] == VERSIONS["coastnet_model"] and \
        sliderule["qtrees"]["model"] == VERSIONS["qtrees_model"] and \
        sliderule["ensemble"]["model"] == VERSIONS["ensemble_model"] and \
        sliderule["cshelph"]["version"] == VERSIONS["cshelph_version"] and \
        sliderule["medianfilter"]["version"] == VERSIONS["medianfilter_version"]):
            raise RuntimeError(f'\n{granule} - failed version check')

        # check for iso xml file
        if granule not in iso_xmls:
            raise RuntimeError(f'\n{granule} - missing ISO XML')

        # build column dictionary
        columns = {f'{var}': [] for var in VARIABLES}
        columns['beam'] = []
        columns['spot'] = []
        for beam in BEAMS:
            try:
                # extend variables
                beam_len = 0
                for var in VARIABLES:
                    dataset = f'{beam}/{var}'
                    data = promise[dataset][:]
                    columns[var].extend(data)
                    beam_len = len(data)
                # extend beam and spot
                spot = BEAM_TO_SPOT[promise["orbit_info/sc_orient"][0]][beam]
                columns['beam'].extend([beam] * beam_len)
                columns['spot'].extend([spot] * beam_len)
            except TypeError:
                # missing beam
                pass

        # close granule
        h5obj.close()

        # build dataframes and info
        df = pd.DataFrame(columns)
        df_sea_surface = df[df["class_ph"] == 41]
        df_bathy = df[df["class_ph"] == 40]
        df_bathy_high = df_bathy[df_bathy["low_confidence_flag"] == 0]
        month = int(granule[10:12])
        region = int(granule[27:29])

        # build stats
        row = {
            "granule": granule,
            "size": size,
            "total_photons": stats["total_photons"],
            "sea_surface_photons": stats["sea_surface_photons"],
            "subaqueous_photons": stats["subaqueous_photons"],
            "bathy_photons": stats["bathy_photons"],
            "bathy_strong_photons": stats["bathy_strong_photons"],
            "bathy_linear_coverage": stats["bathy_linear_coverage"],
            "bathy_mean_depth": stats["bathy_mean_depth"],
            "bathy_min_depth": stats["bathy_min_depth"],
            "bathy_max_depth": stats["bathy_max_depth"],
            "bathy_std_depth": stats["bathy_std_depth"],
            "sea_surface_std": df_sea_surface["ortho_h"].std(),
            "region": region,
            "ascending": REGION_TO_ASCENDING[region],
            "season": MONTH_TO_SEASON[region<8][month]
        } | get_bathy_stats(df_bathy, "bathy") | get_bathy_stats(df_bathy_high, "bathy_high")

        # display progress
        print(".", end='')
        sys.stdout.flush()

        # return csv line
        csv_line = [f'{row[entry[0]]:{entry[1]}}' for entry in STATS]
        return ','.join(csv_line) + "\n"

    except Exception as e:
        print(f'\n{granule} - {e}')
        return ''

# ################################################
# Start Process Workers
# ################################################

granule_step = 1000
for i in range(0, len(granules), granule_step):
    pool = Pool(args.cores)
    for result in pool.imap_unordered(stat_worker, granules[i:i+granule_step]):
        if result != None:
            summary_file.write(result)
            summary_file.flush()
    del pool
