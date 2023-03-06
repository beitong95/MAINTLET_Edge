import alsaaudio
import sys
from MaintletLog import logger

channelNames = ['CH1 digital volume',
                'CH2 digital volume',
                'CH3 digital volume',
                'CH4 digital volume',
                'CH5 digital volume',
                'CH6 digital volume']
currentVolumes = [82,82,82,82,82,82]


def list_cards():
    print("Available sound cards:")
    for i in alsaaudio.card_indexes():
        (name, longname) = alsaaudio.card_name(i)
        print("  %d: %s (%s)" % (i, name, longname))

def set_mixer(name, volume, cardindex = 1):
    global currentVolumes
    # Demonstrates how to set mixer settings
    try:
        mixer = alsaaudio.Mixer(name, cardindex=cardindex)
    except alsaaudio.ALSAAudioError:
        print("No such mixer", file=sys.stderr)
        sys.exit(1)

    # Set volume for specified channel. MIXER_CHANNEL_ALL means set
    # volume for all channels
    volume = int(volume)
    channel = alsaaudio.MIXER_CHANNEL_ALL
    mixer.setvolume(volume, channel)
    currentVolumes[channelNames.index(name)] = int(volume)

def setMultiMixers(volumes, cardindex = 1):
    for channelName,volume in zip(channelNames,volumes):
        set_mixer(channelName, volume, cardindex)

def gainControl(absMax, channelName):
    global currentVolumes
    currentVolume = currentVolumes[channelNames.index(channelName)]
    previousVolume = currentVolume
    newVolume = previousVolume
    if absMax > 0.95:
        newVolume = int(previousVolume * 0.95)
        set_mixer(channelName, newVolume)
    # elif absMax < 0.5:
    #     set_mixer(channelName, int(currentVolume + 1))
        logger.error(f"GAIN CONTROL: Change {channelName} from {previousVolume} to {newVolume}")

if __name__ == '__main__':
    """
    'Headphone'
    'Speaker'
    'ADC1 PGA gain'
    'ADC2 PGA gain'
    'ADC3 PGA gain'
    'ADC4 PGA gain'
    'ADC5 PGA gain'
    'ADC6 PGA gain'
    'ADC7 PGA gain'
    'ADC8 PGA gain'
    'CH1 digital volume'
    'CH2 digital volume'
    'CH3 digital volume'
    'CH4 digital volume'
    'CH5 digital volume'
    'CH6 digital volume'
    'CH7 digital volume'
    'CH8 digital volume'
    'DAC'
    """

    import time 
    setMultiMixers(volumes=currentVolumes)
    print(getCurrentVolumes())
    time.sleep(5)

    name = 'CH2 digital volume'
    volume = 30
    cardindex = 1
    set_mixer(name, volume, 1)
    print(getCurrentVolumes())

    time.sleep(5)
    volumes = [1,2,3,4,5,6]
    setMultiMixers(volumes=volumes)
    print(getCurrentVolumes())
