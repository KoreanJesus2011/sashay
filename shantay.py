#!/usr/bin/python
import bz2
import datetime
import glob
import os
import re
import subprocess
import sys
import tempfile
from CoreFoundation import CFPreferencesCopyAppValue

# #sanity checking - since I'm going through the trouble of pure python bunzip'ing
# plist_path = '/Applications/Server.app/Contents/Info.plist'
# server_app_version = CFPreferencesCopyAppValue('CFBundleShortVersionString', plist_path)
# if not server_app_version:
#     print "Can't find Server.app, are you running this on your Mac server instance?"
#     sys.exit(1)
# elif float(server_app_version) < 4.1:
#     print "Not Version 4.1(+) of Server.app"
#     sys.exit(1)
#
# if os.geteuid() != 0:
#     exit("For the final message send(only), this(currently) needs to be run with 'sudo'.")
    
#gimme some vars
how_far_back = 3
# dir_of_logs='/Library/Server/Caching/Logs'
dir_of_logs = '/Users/abanks/Desktop/cashayScratch/Logs'                        #debug

#time jiggery-pokery
now = str(datetime.datetime.today())[:-3]
delta_object = datetime.timedelta(days=how_far_back)
start_datetime = str(datetime.datetime.today() - delta_object)[:-3] # lops off UTC's millisecs

#data structures for parsing, now and later
bandwidth_lines_list,filetype_lines_list,logged_bytes_from_cache,logged_bytes_from_apple=[],[],[],[]
our_range_logline_str_list,service_restart_timestamps,logged_bytes_from_peers=[],[],[]
IPLog,OSLog,ModelLog,ipas,epubs,pkgs,zips=[],[],[],[],[],[],[]

excludes = ['egist', 'public', 'peers', 'Opened', 'EC', 'Bad']
filetypes = ['ipa', 'epub', 'pkg', 'zip']
#setup tempfile 
unbzipped_logs = tempfile.mkstemp(suffix='.log',prefix='sashayTemp-')[1]
# print unbzipped_logs                                                                #debug
das_bzips = "".join([dir_of_logs, '/Debug-*'])
bunch_of_bzips = glob.glob(das_bzips)
opened_masterlog = open(unbzipped_logs, 'w')
#concat each unbz'd log to tempfile
for archived_log in bunch_of_bzips:
    try:
        process_bz = bz2.BZ2File(archived_log)
        opened_masterlog.write(process_bz.read())
    except Exception as e:
        raise e
    finally:
        process_bz.close()
opened_masterlog.close()

more_recent_svc_hup = False

#main loop to populate data structures 
try:
    with open(os.path.join(dir_of_logs, 'Debug.log'), 'rU') as current, open(unbzipped_logs, 'rU') as unzipped:
        for f in current, unzipped:
            for line in f:
                if line[:23] > start_datetime:
                    our_range_logline_str_list.append(line)
except IOError as e:
    print 'Operation failed: %s' % e.strerror
    sys.exit(1)

for logline_str in our_range_logline_str_list:
    if 'Registration succeeded.  Resuming server.' in logline_str:
        service_restart_timestamps.append(logline_str[:23])
        more_recent_svc_hup = True
        new_start_datetime = max(service_restart_timestamps)

if more_recent_svc_hup:
    for logline_str in our_range_logline_str_list:
        if logline_str[:23] > new_start_datetime:
            if 'start:' in logline_str:
                bandwidth_lines_list.append(logline_str.split())
            elif not any(x in logline_str for x in excludes):
                if any(x in logline_str for x in filetypes):
                    filetype_lines_list.append(logline_str.split())
else:
    for logline_str in our_range_logline_str_list:
        if logline_str[:23] > start_datetime:
            if 'start:' in logline_str:
                bandwidth_lines_list.append(logline_str.split())
            elif not any(x in logline_str for x in excludes):
                if any(x in logline_str for x in filetypes):
                    filetype_lines_list.append(logline_str.split())
#Nitty-gritty
# ['2015-06-30', '12:31:04.095', '#eLTtl5KfMlrA', 'Request', 'from', '172.20.202.245:61917', '[itunesstored/1.0', 'iOS/8.3', 'model/iPhone7,1', 'build/12F70', '(6;', 'dt:107)]', 'for', 'http://a1254.phobos.apple.com/us/r1000/038/Purple7/v4/23/23/5e/23235e5d-1a12-f381-c001-60acfe6a56ff/zrh1611131113630130772.D2.pd.ipa']
# ['2015-06-30', '12:32:19.554', '#6d3LgXpVcHAU', 'Request', 'from', '172.18.20.102:52880', '[Software%20Update', '(unknown', 'version)', 'CFNetwork/720.3.13', 'Darwin/14.3.0', '(x86_64)]', 'for', 'http://swcdn.apple.com/content/downloads/58/34/031-25780/u1bqpe4ggzdp86utj2esnxfj4xq5izwwri/FirmwareUpdate.pkg']
# ['2015-06-30', '14:09:00.230', '#sNn+egdFxN7m', 'Request', 'from', '172.18.81.204:60025', '[Software%20Update', '(unknown', 'version)', 'CFNetwork/596.6.3', 'Darwin/12.5.0', '(x86_64)', '(MacBookAir6%2C2)]', 'for', 'http://swcdn.apple.com/content/downloads/15/59/031-21808/qylh17vrdgnipjibo2avj3nbw8y2pzeito/Safari6.2.7MountainLion.pkg']
for filelog in filetype_lines_list:
    if filelog[5].startswith('172'):
        strip_port = (filelog[5])[:-6]
        IPLog.append(strip_port)
        if filelog[10].startswith('Darwin/12'):
            OSLog.append('Mac OS 10.8.x')
        elif filelog[10].startswith('Darwin/13'):
            OSLog.append('Mac OS 10.9.x')
        elif filelog[10].startswith('Darwin/14'):
            OSLog.append('Mac OS 10.10.x')
        else:
            OSLog.append(filelog[7])
        if len(filelog) == 15:
            ModelLog.append(filelog[12])
        elif filelog[7] == '(unknown':
            ModelLog.append('Unknown Mac')
        else:
            ModelLog.append(filelog[8])
        if (filelog[12]).endswith('ipa'):
            ipas.append(filelog[12])
        elif (filelog[12]).endswith('epub'):
            epubs.append(filelog[12])
        elif (filelog[12]).endswith('pkg'):
            pkgs.append(filelog[12])
        elif (filelog[12]).endswith('zip'):
            zips.append(filelog[12])

#normalize to GBs
def normalize_gbs(mb_or_gb, val_to_operate_on):
    """take an index to check, and if MB, return applicable index divided by 1024"""
    if mb_or_gb == 'MB':
        return float(float(val_to_operate_on) / 1024.0)
    elif mb_or_gb != 'GB':
        return 0.0 # if it's less than 1MB just shove in a placeholder float
    else:
        return float(val_to_operate_on)

def alice(list_to_get_extremes):
    """one pill makes you taller"""
    return max(list_to_get_extremes) - min(list_to_get_extremes)

for each in bandwidth_lines_list:
    strip_parens = (each[15])[1:] # silly log line cleanup
    logged_bytes_from_cache.append(normalize_gbs(each[6], each[5]))
    logged_bytes_from_apple.append(normalize_gbs(each[16], strip_parens))
    if not each[19] == '0':
        logged_bytes_from_peers.append(normalize_gbs(each[20], each[19]))
daily_total_from_cache = alice(logged_bytes_from_cache)
daily_total_from_apple = alice(logged_bytes_from_apple)

def gen_mb_or_gb(float):
    """based on how big the results of a calc is, either display float and GBs
       or multiply times 1024 and display in MBs"""
    if float > 1.0:
        return " ".join([str(round(float, 2)), 'GBs'])
    else:
        return " ".join([str(round(float * 1024), 2), 'MBs'])

if len(logged_bytes_from_peers) > 1:
    if max(logged_bytes_from_peers) > 0.1:
        daily_total_from_peers = alice(logged_bytes_from_peers)
        daily_total_from_apple = daily_total_from_apple - daily_total_from_peers
        peer_amount = 'along with %s from peers' % gen_mb_or_gb(daily_total_from_peers)
else:
    peer_amount = 'no peer servers detected'

#build message
message = ["Download requests served from cache: ", gen_mb_or_gb(daily_total_from_cache), '\n',
    "Amount streamed from Apple (", peer_amount, "): " , gen_mb_or_gb(daily_total_from_apple), '\n',
    "(Potential) Net bandwidth saved (items could have been cached previously): ",
    gen_mb_or_gb(daily_total_from_cache - daily_total_from_apple), '\n', ""]
if more_recent_svc_hup:
    disclaimer = ['\n', "  * NOTE: Stats are only gathered from last time service was restarted, ", new_start_datetime]
    message += disclaimer
print(' '.join(message))                                                        #debug
print OSLog + ModelLog                                                          #debug
print set(IPLog)
# subprocess.call('/Applications/Server.app/Contents/ServerRoot/usr/sbin/server postAlert CustomAlert Common subject "Caching Server Data: Today" message "' + ' '.join(message) + '" <<<""', shell=True)