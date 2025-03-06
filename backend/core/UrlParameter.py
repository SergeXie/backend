from configparser import ConfigParser

config = ConfigParser()
config.read('config.ini')
config_content = {}
for section in config.sections():
    config_content[section] = dict(config.items(section))

class UrlParameter:
    url_map_dict=config_content['URLmap']

    def __init__(self):
        pass

    def get_url_map(self, originalurl: str):
        return self.url_map_dict[originalurl]

    def get_url_keys(self):
        return self.url_map_dict.keys()

