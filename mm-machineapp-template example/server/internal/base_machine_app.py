from abc import ABC, abstractmethod
import logging
from internal.notifier import NotificationLevel, sendNotification
import time
from internal.mqtt_topic_subscriber import MqttTopicSubscriber

# TODO: Hacky wait to ensure that all print statements are immediately flushed up to the super-process
import functools
print = functools.partial(print, flush=True)

class MachineAppState(ABC):
    '''
    Abstract class that defines a MachineAppState. If you want to create a new state,
    you will inherit this class and implement, at the minimum, the onEnter and onLeave
    methods. See IdleState for an example.
    '''
    
    def __init__(self, engine: 'BaseMachineAppEngine'):
        '''
        Constructor will be executed when you click the Play button. This will be executed
        only ONCE at the beginning of your entire program.
        '''
        self.logger = logging.getLogger(__name__)
        self.engine = engine
        self.configuration = self.engine.getConfiguration()

        self.__mqttTopicSubscriberList = []

    def gotoState(self, state):
        '''
        Updates the MachineAppEngine to the provided state

        params:
            newState: str
                name of the state that you would like to transition to
        returns:
            bool
                successfully moved to the new state
        '''
        return self.engine.gotoState(state)

    def registerCallback(self, machineMotion: 'MachineMotion', ioName: str, callback):
        ''' 
        Register a callback for a particular topic. Note that you should call removeCallback
        when you are finished.

        params:
            machineMotion: MachineMotion
                Machine whose MQTT topic you want to subscribe to

            ioName: str
                Friendly IO name that you would like to subscribe to

            callback: func(topic: str, msg: str) -> void
                Callback that gets called when we receive data on that topic
        '''
        mqttSubscriber = None
        for subscriber in self.__mqttTopicSubscriberList:
            if subscriber.getMachineMotion() == machineMotion:
                mqttSubscriber = subscriber
                break

        if mqttSubscriber == None:
            mqttSubscriber = MqttTopicSubscriber(machineMotion)
            self.__mqttTopicSubscriberList.append(mqttSubscriber)

        mqttSubscriber.registerCallback(machineMotion.getInputTopic(ioName), callback)

    @abstractmethod
    def onEnter(self):
        ''' 
        Called whenever this state is entered
        '''
        pass

    def onLeave(self):
        ''' Called when we're transitioning out of this state '''
        pass

    def update(self):
        '''
        Called continuously while this state is active
        
        Default behavior: Do nothing
        '''
        pass

    def onPause(self):
        '''
        Called whenever we pause while we're in this state

        Default behavior: Do nothing
        
        '''
        pass

    def onResume(self):
        '''
        Called whenever we resume while we're in this state
        
        Default behavior: Do nothing
        '''
        pass

    def onStop(self):
        ''' 
        Called whenever we stop while we're in this state 

        Default behavior: Reset the engine state to the beginning of the state machine
        '''
        pass

    def updateCallbacks(self):
        '''
        Warning: For internal use only.

        Updates all of the MQTT topic subscribers that you currently have active.
        '''
        for subscriber in self.__mqttTopicSubscriberList:
            subscriber.update()

    def freeCallbacks(self):
        '''
        Warning: For internal use only.

        Deletes all of the MQTT topic subscribers that you currently have active.
        '''
        for subscriber in self.__mqttTopicSubscriberList:
            subscriber.delete()

        self.__mqttTopicSubscriberList.clear()

class BaseMachineAppEngine(ABC):
    '''
    Base class for the MachineApp engine
    '''
    UPDATE_INTERVAL_SECONDS = 0.16

    def __init__(self):
        self.configuration  = None                                      # Python dictionary containing the loaded configuration payload
        self.logger         = logging.getLogger(__name__)               # Logger used to output information to the local log file and console
        
        # High-Level state variables
        self.__isRunning              = False                           # The MachineApp will execute while this flag is set
        self.__isPaused               = False                           # The machine app will not do any state updates while this flag is set
        self.__stateDictionary      = {}                                # Mapping of state names to MachineAppState definitions
        self.__currentState         = None                              # Active state of the engine
        self.__nextRequestedState   = None                              # If set, we will transition into the provided state
        self.__inStateStepperMode   = False                             # If True, the engine will enter a Pause state in between each state transition
        self.__hasPausedForStepper  = False                             # Keeps track of whether or not we have allowed stepper mode to pause the app between transitions
        
        # Transitional state variables
        self.__shouldStop   = False                                     # Tells the MachineApp loop that it should stop on its next update
        self.__shouldPause  = False                                     # Tells the MachineApp loop that it should pause on its next update
        self.__shouldResume = False                                     # Tells the MachineApp loop that it should resume on its next update


    @abstractmethod
    def initialize(self):
        ''' 
        Called when you hit play. In this method, you will
        initialize your machine motion instances and configure them. You
        may also define variables that you'd like to access and manipulate
        over the course of your MachineApp here.
        '''
        pass

    @abstractmethod
    def getDefaultState(self):
        '''
        Returns the state that your Application begins in when a run begins. This string MUST
        map to a key in your state dictionary.

        returns:
            str
        '''
        return None

    @abstractmethod
    def buildStateDictionary(self):
        '''
        Builds and returns a dictionary that maps state names to MachineAppState.
        The MachineAppState class wraps callbacks for stateful transitions in your MachineApp.

        returns:
            dict<str, MachineAppState>
        '''
        return {}

    @abstractmethod
    def afterRun(self):
        '''
        Executed when execution of your MachineApp ends (i.e., when self.__isRunning goes from True to False).
        This could be due to an estop, stop event, or something else.

        In this method, you can clean up any resources that you'd like to clean up, or do nothing at all.
        '''
        pass

    @abstractmethod
    def onStop(self):
        '''
        Called when a stop is requested from the REST API.
        '''
        pass

    @abstractmethod
    def onPause(self):
        '''
        Called when a pause is requested from the REST API.
        '''
        pass

    @abstractmethod
    def onResume(self):
        '''
        Called when a resume is requested from the REST API.
        '''
        pass

    @abstractmethod
    def onEstop(self):
        '''
        Called AFTER the MachineMotion has been estopped. Please note that any state
        that you were using will no longer be available at this point. You should
        most likely reset all IOs to the OFF position in this method.
        '''
        pass

    def getConfiguration(self):
        ''' Returns the current configuration '''
        return self.configuration

    def getCurrentState(self):
        '''
        Returns the implementation of MachineAppState that maps to the value of self.__currentState.
        If the mapping is invalid, we return None and log an error.

        returns:
            MachineAppState
        '''
        if self.__currentState == None:
            self.logger.error('Current state is none')
            return None

        if not self.__currentState in self.__stateDictionary:
            self.logger.error('Trying to retrieve an unknown state: {}'.format(self.__currentState))
            return None

        return self.__stateDictionary[self.__currentState]
        
    def gotoState(self, newState: str):
        '''
        Updates the MachineAppEngine to the provided state

        params:
            newState: str
                name of the state that you would like to transition to
        returns:
            bool
                successfully moved to the new state
        '''
        if not newState in self.__stateDictionary:
            self.logger.error('Trying to move to an unknown state: {}'.format(newState))
            return False

        self.__nextRequestedState = newState
        return True

    def __tryExecuteStateTransition(self):
        '''
        (Internal, for engine use only)
        
        This internal method will actually transition the state machine
        into the state that was requested by 'gotoState'.

        If we are in 'state stepper mode', we will first pause the machine.
        '''
        if self.__nextRequestedState == None:
            return False

        if self.__inStateStepperMode and not self.__hasPausedForStepper:
            self.pause()
            self.__hasPausedForStepper = True
            return True # Return True so that we can get a clean update loop

        self.__hasPausedForStepper = False # We have paused for the stepper at this point, so let's reset it

        if not self.__currentState == None:
            prevState = self.getCurrentState()
            if prevState != None:
                prevState.onLeave()
                prevState.freeCallbacks()

        sendNotification(NotificationLevel.APP_STATE_CHANGE, 'Entered MachineApp state: {}'.format(self.__nextRequestedState))
        self.__currentState = self.__nextRequestedState
        self.__nextRequestedState = None
        nextState = self.getCurrentState()

        if nextState != None:
            nextState.onEnter()

        return True

    def loop(self, inStateStepperMode, configuration):
        '''
        Main loop of your MachineApp.
        '''
        if self.__isRunning:
            return False

        sendNotification(NotificationLevel.APP_START, 'MachineApp started')
        self.logger.info('Starting the main MachineApp loop')

        # Configure run time variables
        self.__inStateStepperMode = inStateStepperMode
        self.configuration = configuration
        self.__isRunning = True

        # Run initialization sequence
        self.initialize()
        self.__stateDictionary = self.buildStateDictionary()

        # Begin the Application by moving to the default state
        self.gotoState(self.getDefaultState())

        # Inner Loop running the actual MachineApp program
        while self.__isRunning:
            if self.__shouldStop:           # Running stop behavior
                self.__shouldStop = False
                self.__isRunning = False

                self.onStop()

                currentState = self.getCurrentState()
                if currentState != None:
                    currentState.onStop()
                
                break

            if self.__shouldPause:          # Running pause behavior
                if self.__hasPausedForStepper:
                    sendNotification(NotificationLevel.APP_PAUSE, 'Paused for stepper mode: Moving from {} state to {} state'.format(self.__currentState, self.__nextRequestedState))
                else:
                    sendNotification(NotificationLevel.APP_PAUSE, 'MachineApp paused')

                self.__shouldPause = False
                self.__isPaused = True

                if not self.__hasPausedForStepper: # Only do pause behavior if we're not doing the stepper-mandated pause
                    self.onPause()

                    currentState = self.getCurrentState()
                    if currentState != None:
                        currentState.onPause()

            if self.__shouldResume:         # Running resume behavior
                sendNotification(NotificationLevel.APP_RESUME, 'MachineApp resumed')
                self.__shouldResume = False
                self.__isPaused = False

                if not self.__hasPausedForStepper: # Only do resume behavior if we're not doing the stepper-mandated pause
                    self.onResume()

                    currentState = self.getCurrentState()
                    if currentState != None:
                        currentState.onResume()

            if self.__isPaused:               # While paused, don't do anything
                time.sleep(BaseMachineAppEngine.UPDATE_INTERVAL_SECONDS)
                continue

            if self.__nextRequestedState != None:       # Running state transition behavior
                if self.__tryExecuteStateTransition():
                    continue # If the transition is executed successfully, let's get a clean update loop

            currentState = self.getCurrentState()
            if currentState == None:
                self.logger.error('Currently in an invalid state')
                continue

            currentState.updateCallbacks()
            currentState.update()

            time.sleep(BaseMachineAppEngine.UPDATE_INTERVAL_SECONDS)

        self.logger.info('Exiting MachineApp loop')
        sendNotification(NotificationLevel.APP_COMPLETE, 'MachineApp completed')
        self.afterRun()
        return True

    def pause(self):
        '''
        Pauses the MachineApp loop.
        
        Warning: Logic in here is happening in a different thread. You should only 
        alter this behavior if you know what you are doing. It is recommended that
        you implement any on-pause behavior in your MachineAppStates instead
        '''
        self.logger.info('Pausing the MachineApp')
        self.__shouldPause = True

    def resume(self):
        '''
        Resumes the MachineApp loop.
        
        Warning: Logic in here is happening in a different thread. You should only 
        alter this behavior if you know what you are doing. It is recommended that
        you implement any on-resume behavior in your MachineAppStates instead
        '''
        self.logger.info('Resuming the MachineApp')
        self.__shouldResume = True

    def stop(self):
        '''
        Stops the MachineApp loop.
        
        Warning: Logic in here is happening in a different thread. You should only 
        alter this behavior if you know what you are doing. It is recommended that
        you implement any on-stop behavior in your MachineAppStates instead
        '''
        self.logger.info('Stopping the MachineApp')
        self.__shouldStop = True