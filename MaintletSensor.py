class MaintletSensor:
    def __init__(self, setting):
        """
        Init a Maintlet sensor

        Args:
            setting (dict): a dictionary contains setting of a sensor
                - If you want to add attribute, please change the ini file and Sensor.py
        """        
        self.type = setting['type']
        self.location = setting['location']
        if self.type == 'NC':
            self.location = ''
