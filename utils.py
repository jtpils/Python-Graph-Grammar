import random
import logging
import logging.config
import yaml
from typing import Iterable, Sized


logging_configured = False

class Bidict(dict):
    """
    This class implements a bidirectional dict, where the other direction can be optained by bi_dict.inverse.

    This comes from https://stackoverflow.com/a/21894086.
    """
    def __init__(self, *args, **kwargs):
        super(Bidict, self).__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse.setdefault(value,[]).append(key)

    def __setitem__(self, key, value):
        if key in self:
            self.inverse[self[key]].remove(key)
        super(Bidict, self).__setitem__(key, value)
        self.inverse.setdefault(value,[]).append(key)

    def __delitem__(self, key):
        self.inverse.setdefault(self[key],[]).remove(key)
        if self[key] in self.inverse and not self.inverse[self[key]]:
            del self.inverse[self[key]]
        super(Bidict, self).__delitem__(key)


def randomly(objects: Sized and Iterable):
    shuffled = list(objects)
    random.shuffle(shuffled)
    return shuffled


def config_logging():
    with open('logging_config.yml', 'r') as file:
        log_conf_dict = yaml.safe_load(file)
    logging.config.dictConfig(log_conf_dict)


def get_logger(name, handler=None):
    if not logging_configured:
        config_logging()
    logger = logging.getLogger(name)
    if handler is None:
        logger.addHandler(logging.NullHandler())
    else:
        logger.addHandler(handler)
    return logger
