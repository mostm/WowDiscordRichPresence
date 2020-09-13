from PIL import ImageGrab
import pypresence
import time
import logging
import traceback

from time import sleep
import ftfy
import psutil


from data import large_image_instanceMapID, name_classID, large_image_mapID, large_image_zone, \
    small_image_classID, size_difficultyID

# config
discord_client_id = '429296102727221258'  # Put your Client ID here
msg_header = "ARW"
max_msg_len = 900
MAX_LEVEL = 110

# logging
logger = logging.getLogger('wowdrp')
hdlr = logging.FileHandler('wowdrp.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)


def get_process(name):
    for pid in psutil.pids():
        try:
            a = psutil.Process(pid)
        except psutil.NoSuchProcess:
            # means nada
            continue
        if a.name().endswith(name):
            return a


def get_wow_process():
    return get_process('Wow.exe')


def iterate_pixels(pixels, channel):
    line = ""
    wait_for_null = False

    if channel.lower() == 'r':
        channel_index = 0
    elif channel.lower() == 'g':
        channel_index = 1
    elif channel.lower() == 'b':
        channel_index = 2
    else:
        raise ValueError("Unknown color channel: {0}".format(channel))

    for p in pixels:
        channels = p
        character_ordinal = channels[channel_index]
        if character_ordinal == 0:
            # We've reached a null separator; look for a character again
            wait_for_null = False
        elif wait_for_null is False:
            # Cool, this is a character. Due to UI Scale, this character may repeat immediately
            # afterwards. Thus, wait for a null separator before continuing to parse.
            line += chr(character_ordinal)
            wait_for_null = True

    return line

# reads message character by character using all 3 color channels
def parse_pixels(pixels):
    msg = ""
    msg += iterate_pixels(pixels, 'r')
    msg += iterate_pixels(pixels, 'g')
    msg += iterate_pixels(pixels, 'b')
    logger.info("Raw message: %s" % (msg,))
    msg = ftfy.fix_text(msg)
    logger.info("Decoded message: %s" % (msg,))
    return msg


# gets pixel data from screenshot
def read_screen():
    img = ImageGrab.grab(bbox=(0, 0, max_msg_len / 3, 1))
    pixels = list(img.getdata())
    return pixels


def get_msg():
    px = read_screen()
    msg = parse_pixels(px)
    if msg[:3] == msg_header:
        logger.info("Message is valid")
        return msg[3:]
    else:
        logger.info("Message is junk")
        return None


def parse_msg(msg):
    ms = msg.split("|")
    total = msg.count('|')
    if total < 14:
        logger.info('Total amount of entries is lower than parser was designed for. (reason: char limit)')
    i = 0
    entries = ['name', 'realm', 'classID', 'race', 'level', 'itemLevel', 'mapAreaID', 'instanceMapID', 'zone', 'miniMapZoneText', 'numGroupMembers', 'maxGroupMembers', 'difficultyID', 'status', 'timeStarted']
    time_started = -1
    wow_proc = get_process('Wow.exe')
    if wow_proc:
        time_started = int(wow_proc.create_time())
    data = { # fallback values, if parcing wasn't successful.
        'name': '',
        'realm': '',
        'classID': 0,
        'race': '',
        'level': 0,
        'itemLevel': 0,
        'mapAreaID': 0,
        'instanceMapID': 0,
        'zone': '',
        'miniMapZoneText': '',
        'numGroupMembers': 0,
        'maxGroupMembers': 0,
        'difficultyID': 0,
        'status': 'In World',
        'timeStarted': time_started
    }
    for i in range(0, total):
        data[entries[i]] = type(data[entries[i]])(ms[i])
    logger.info("Successfully parsed message into dict")
    return data


def format_state(data):
    return data["status"]


def format_details(data):
    return "%s - %s" % (data["name"], data["realm"])


def format_large_text(data):
    if data["classID"] == 4 and data["level"] > 97 and data["miniMapZoneText"] in large_image_zone:
        return "The Hall of Shadows"
    return data["zone"]


def format_large_image(data):
    try:  # check for rogue class hall
        if data["classID"] == 4 and data["level"] > 97:
            return large_image_zone[data["miniMapZoneText"]]
    except: pass
    try:  # check for other class halls
        if data["level"] > 97:
            return large_image_zone[data["zone"]]
    except: pass
    try:  # check for cities
        return large_image_mapID[data["mapAreaID"]]
    except: pass
    try:  # check for dungeons and raids
        return large_image_instanceMapID[data["instanceMapID"]]
    except: pass
    # default
    return "cont_azeroth"


def format_small_text(data):
    race = data["race"]
    if race == "NightElf":
        race = "Night Elf"
    elif race == "BloodElf":
        race = "Blood Elf"
    elif race == "VoidElf":
        race = "Void Elf"
    elif race == "LightforgedDraenei":
        race = "Lightforged Draenei"
    elif race == "HighmountainTauren":
        race = "Highmountain Tauren"
    level = data["level"]
    if level == MAX_LEVEL:
        level = "ilvl " + str(data["itemLevel"])
    return "%s %s %s" % (str(level), race, name_classID[data["classID"]])


def format_small_image(data):
    try:
        return small_image_classID[data["classID"]]
    except:
        logger.error("Invalid class for small icon")
        return "icon_full"


def format_start(data):
    if data["timeStarted"] != -1:
        return data["timeStarted"]
    return None


def format_party_size(data):
    if data["numGroupMembers"] == 0 or data["maxGroupMembers"] == 0:
        return None
    return [data["numGroupMembers"], data["maxGroupMembers"]]


def start_drp():
    rpc = pypresence.Presence(discord_client_id)
    rpc.connect()
    last_msg = ""
    while True:  # The presence will stay on as long as the program is running
        try:
            msg = get_msg()
            wow_proc = get_wow_process()
            if not msg and not wow_proc:
                rpc.clear()
            if not msg and wow_proc:
                rpc_update = {
                    'pid': wow_proc.pid,
                    'state': 'Main Menu',
                    'details': 'Selecting a character',
                    'start': int(wow_proc.create_time()),
                }
                rpc.update(**rpc_update)
            if msg and last_msg != msg:
                print("Msg: " + msg)
                data = parse_msg(msg)
                rpc_update = {
                    'state': format_state(data),
                    'details': format_details(data),
                    'start': format_start(data),
                    'large_image': format_large_image(data),
                    'large_text': format_large_text(data),
                    'small_image': format_small_image(data),
                    'small_text': format_small_text(data),
                    'party_size': format_party_size(data)
                }
                if wow_proc:
                    rpc_update['pid'] = wow_proc.pid
                rpc.update(**rpc_update)
                if last_msg == "":
                    sleep(3)
                    rpc.update(**rpc_update)
                last_msg = msg
                logger.info("Successfully updated discord activity")
        except Exception:
            logger.exception("Exception in Main Loop")
            logger.exception("Exception: " + traceback.format_exc())
            print("Exception in Main Loop")
            print("Exception: " + traceback.format_exc())
        time.sleep(1)

start_drp()
