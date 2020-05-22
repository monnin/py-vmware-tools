import argparse

#
#	Taken from
#
#		https://guido.vonrudorff.de/2013/python-argparse-graceful-parameter-parsing/
#

class forgive_choice_list(object):
    def __init__(self, iterable):
        self._choices = [str(i) for i in iterable]

    def __contains__(self, item):
        return bool(self.expand(item))

    def __iter__(self):
        return iter(self._choices)

    def expand(self, item):
        if item in self._choices:
            return item
        candidates = [x for x in self._choices if x.startswith(item)]
        if len(candidates) == 1:
            return candidates[0]
        else:
            return None

class forgive_choice_action(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, self.choices.expand(values))
