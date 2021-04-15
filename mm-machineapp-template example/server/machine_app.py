#/usr/bin/python3

from env import env
import logging
import time
from internal.base_machine_app import MachineAppState, BaseMachineAppEngine
#new from template needed in this program 
from internal.notifier import NotificationLevel, sendNotification, getNotifier
# from internal.io_monitor import IOMonitor
from sensor import Sensor
from digital_out import Digital_Out
from pneumatic import Pneumatic
#from math import ceil, sqrt #we will not need math

'''
If we are in development mode (i.e. running locally), we Initialize a mocked instance of machine motion.
This fake MachineMotion interface is used ONLY when developing locally on your own machine motion, so
that you have a good idea of whether or not your application properly builds.
''' 
if env.IS_DEVELOPMENT:
    from internal.fake_machine_motion import MachineMotion
else:
    from internal.machine_motion import MachineMotion

class MachineAppEngine(BaseMachineAppEngine):
    ''' Manages and orchestrates your MachineAppStates '''

    def buildStateDictionary(self):
        '''
        Builds and returns a dictionary that maps state names to MachineAppState.
        The MachineAppState class wraps callbacks for stateful transitions in your MachineApp.

        Note that this dictionary is built when your application starts, not when you click the
        'Play' button.

        returns:
            dict<str, MachineAppState>
        '''
    
        stateDictionary = {
            'Initialize'            : InitializeState(self),
            'Feed_New_Roll'         : FeedNewRollState(self),
            'Roll'                  : Roll(self),
            'Clamp'                 : Clamp(self),
            'Cut'                   : Cut(self),
            'Home'                  : HomingState(self), #home state rollers need to be down
            'First_Roll'            : First_Roll(self)
        

        }

        return stateDictionary
     
    def getDefaultState(self):
            return 'Initialize'
    
    def initialize(self):
        self.logger.info('Running initialization')
        
        # Create and configure your machine motion instances
        mm_IP = '192.168.7.2' #127.0.0.1 this is the fake machine IP address
        self.MachineMotion = MachineMotion(mm_IP)
        # Timing Belts 
        self.timing_belt_axis = 1 #is this the actuator number? Yes
        self.MachineMotion.configAxis(self.timing_belt_axis, 8, 150) #150 is for mechanical gain for timing belt. If gearbox used then divide by 5
        self.MachineMotion.configAxisDirection(self.timing_belt_axis, 'positive')
        #Rollers
        # self.roller_axis = 2
        # self.MachineMotion.configAxis(self.roller_axis, 8, 319.186) 
        # self.MachineMotion.configAxisDirection(self.roller_axis, 'positive')
        #pneumatics
        dio1 = mm_IP
        dio2 = mm_IP
        
        self.knife_pneumatic = Pneumatic("Knife Pneumatic", ipAddress=dio1, networkId=1, pushPin=0, pullPin=1)     
        self.roller_pneumatic = Pneumatic("Roller Pneumatic", ipAddress=dio2, networkId=2, pushPin=0, pullPin=1) 
        self.plate_pneumatic = Pneumatic("Plate Pneumatic", ipAddress=dio2, networkId=2, pushPin=2, pullPin=3)
        
        #outputs
        self.knife_output = Digital_Out("Knife Output", ipAddress=dio1, networkId=1, pin=0) #double check correct when knife installed

        #Setup your global variables
        Length = input() #this will need to be tied to the UI
        Num_of_sheets = input() #this will need to be tied to the UI
        Roller_speed = 100 #100 is max roller speed; can be lower
        Roller_accel = 100
        TimingBelt_speed = 900
        TimingBelt_accel = 850
        scrap_distance = 350 #distance from roller to blade 
        flag = 0 #this will note if a new roll is in place


    def onStop(self):
        '''
        Called when a stop is requested from the REST API. 99% of the time, you will
        simply call 'emitStop' on all of your machine motions in this methiod.

        Warning: This logic is happening in a separate thread. EmitStops are allowed in
        this method.
        '''
        self.MachineMotion.emitStop()
        self.knife_output.low() #knife goes down
        #self.roller_pneumatic.release() #this will release the pneumatics and lower the rollers
        self.roller_pneumatic.pull() #rollers up
        self.plate_pneumatic.pull() #plate up 
        self.MachineMotion.emitHome(self.timing_belt_axis) #knife goes to home
       
    def onPause(self):
        '''
        Called when a pause is requested from the REST API. 99% of the time, you will
        simply call 'emitStop' on all of your machine motions in this methiod.
        
        Warning: This logic is happening in a separate thread. EmitStops are allowed in
        this method.
        '''
        self.MachineMotion.emitStop() 
    
    
    def beforeRun(self):
        '''
        Called before every run of your MachineApp. This is where you might want to reset to a default state.
        '''
    
    #Can I add below? no
    # '''
    #     #check if there is a roll,
    #     self.knife_output.low()
    #     self.roller_pneumatic.pull()
    #     self.plate_pneumatic.pull()
    #     self.engine.MachineMotion.emitHome(self.timing_belt_axis)
    # '''
        pass
        
       
    
    def afterRun(self):
        '''
        Executed when execution of your MachineApp ends (i.e., when self.isRunning goes from True to False).
        This could be due to an estop, stop event, or something else.

        In this method, you can clean up any resources that you'd like to clean up, or do nothing at all.
        '''
        pass

    def getMasterMachineMotion(self):
        '''
        Returns the primary machine motion that will be used for estop events.

        returns:
            MachineMotion
        '''
        return self.MachineMotion

class Initialize(MachineAppState):
    '''
    #Puts everything back to the initalizing position. ie knife in home, blade down, pneumatics up 
    '''
    def __init__(self, engine):
        super().__init__(engine)

    def onEnter(self):
        # Change below to ask for inputs
        self.knife_output.low()
        time.sleep(0.1) #make the seconds a variable such as knife wait 
        #self.engine.MachineMotion.waitForMotionCompletion() #is this correct usage? no 
        #self.engine.MachineMotion.emitAbsoluteMove(self.timing_belt_axis,0) #moves timing belt to Home position (0)
        self.engine.MachineMotion.emitHome(self.timing_belt_axis) #does same function as above
        self.notifier.sendMessage(NotificationLevel.INFO,'Knife moving to home')
        self.roller_pneumatic.pull()
        self.plate_pneumatic.pull()
        #self.notifier.sendMessage(NotificationLevel.INFO,'Pneumatics Up')
        
        # Ask for user 
        self.gotoState('Feed_New_Roll')
    
    def update(self): 
        pass    

class Feed_New_Roll(MachineAppState):
    ''' Starts with the clamps up to feed roll. This class is called after the sensor senses there is no more Roll'''
    
    def __init__(self, engine):
        super().__init__(engine)

    def onEnter(self):
        self.knife_output.low()
        time.sleep(0.5) #make the seconds a variable such as knife wait 
        self.engine.MachineMotion.emitHome(self.timing_belt_axis)
        self.roller_pneumatic.pull()
        self.plate_pneumatic.pull()
        
        #wait for input. need to add UI button. When input received, 'Roll Loaded' 
        #when users load a new roll they will tape the edges together. 
        #load material to the rollers
        self.roller_pneumatic.push()

        #if flag set = 1 called First Roll
        #possibly add code to first roll state
        
        self.gotoState('First_Roll')
    
    def update(self): 
        pass    
    
class First_Roll(MachineAppState):
    ''' Rolls material enought to cut first roll and scrap that first piece'''
    def __init__(self, engine):
        super().__init__(engine)

    def onEnter(self):
        self.engine.MachineMotion.emitRelativeMove(self.roller_axis,scrap_distance)    #scrap distance defined in global variables
        Num_of_sheets + 1 #this makes sure we remove this cut from our count
        self.gotoState('Clamp')

    def update(self): 
        pass

class Home(MachineAppState): 
    '''
    Homes our primary machine motion, and sends a message when complete.
    '''
    def __init__(self, engine):
        super().__init__(engine)

    def onEnter(self):
        self.knife_output.low()
        time.sleep(0.5) #make the seconds a variable such as knife wait 
        self.engine.MachineMotion.emitSpeed(TimingBelt_speed)
        self.engine.MachineMotion.emitAcceleration(TimingBelt_accel)
        self.engine.MachineMotion.emitAbsoluteMove(self.timing_belt_axis,0) #moves timing belt to Home position (0)
        #self.notifier.sendMessage(NotificationLevel.INFO,'Knife moving to home')
        self.roller_pneumatic.release()
        #self.notifier.sendMessage(NotificationLevel.INFO,'Rollers Released')
        #is there a roll? yes
        self.gotoState('Roll')
        #is there a roll? No
        self.gotoState ('Feed_New_Roll')
        
    #def onResume(self):
    #    self.gotoState('Initialize')    #I don't remember why this is here
    
    def update(self): 
        pass    
    
            
class Roll(MachineAppState):
    '''
    Activate rollers to roll material
    '''
    def __init__(self, engine):
        super().__init__(engine) 

    def onEnter(self):
    #check sensor to see if there is still a roll

    # If there is a roll then continue, 
    # if not,

        self.MachineMotion.emitStop()
        self.gotoState('Feed_New_Roll')
        #check last cut to see if it was finished
        #if not, create pop up notification to check last cut

        # if sensor triggered:
            # trigger pull or push
            # this can be used for both roller and plate

        # knife pneumatic on release 

        self.knife_output.low()
        self.engine.MachineMotion.emitAbsoluteMove(self.timing_belt_axis,0)
        self.engine.MachineMotion.emitSpeed(Roller_speed)
        self.engine.MachineMotion.emitAcceleration(Roller_accel)
        self.engine.MachineMotion.emitRelativeMove(self.roller_axis,distance) #Distance will be pulled from Global Variable Length input
        self.engine.MachineMotion.waitForMotionCompletion()
        #is there a roll? yes
        self.gotoState('Clamp')
        #is there enough to cut? Ask for user input
        #if yes go to clamp
        #if no go to load roll

    def update(self):
        pass
        
        
class Clamp(MachineAppState):
    def __init__(self, engine):
        super().__init__(engine) 

    def onEnter(self):
    #check sensor to see if there is still a roll. not needed anymore 

    # If there is a roll then continue, flag = 0
    # if not, flag = 1
    # If flag = 1 
    # self.MachineMotion.emitStop()
    # self.gotoState('Feed_New_Roll')

    #check last cut to see if it was finished
    #if last cut did finish go to class feed new roll then first roll where we scrap first piece. 
    #After last cut check if there is more fabric. Move this comment later

    #before cut we check and before roll check for roll 
    #if not, create pop up notification to check scrap last cut 
    
    # if self.knife_output.low() = false
    #     self.knife_output.low()

        self.knife_output.low()
        self.engine.MachineMotion.emitAbsoluteMove(self.timing_belt_axis,0)
        self.engine.MachineMotion.waitForMotionCompletion() #is this correct?
        self.plate_pneumatic.push()
    
        self.gotoState('Cut')

    def update(self):
        pass


class Cut(MachineAppState):
    def __init__(self, engine):
        super().__init__(engine) 
        
    def onEnter(self):
        self.engine.MachineMotion.emitAbsoluteMove(self.timing_belt_axis,0)
        self.engine.MachineMotion.waitForMotionCompletion() #is this correct? yes
        self.knife_output.high() #is this correct to bring knife up? yes
        self.engine.MachineMotion.emitSpeed(TimingBelt_speed)
        self.engine.MachineMotion.emitAcceleration(TimingBelt_accel)
        self.engine.MachineMotion.emitRelativeMove(self.timing_belt_axis, "positive",1900) 
        self.engine.MachineMotion.waitForMotionCompletion()
        self.knife_output.low()
        
        Num_Sheets - 1
        
        if Num_Sheets > 0:
        
            self.gotoState('Home')
        
        else:
            self.engine.stop()
    

    def update(self):
        pass

    
