import os
class Environment:
    '''
    Holds app-wide global variables.
    '''
    # IS_DEVELOPMENT = not os.path.isdir('/var/lib/cloud9')
    # IS_DEVELOPMENT = False
    IS_DEVELOPMENT = False

env = Environment()