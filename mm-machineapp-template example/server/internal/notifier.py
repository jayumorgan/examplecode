import websockets
import asyncio
from threading import RLock, Thread
import logging
import json
import time
from internal.interprocess_message import sendSubprocessToParentMsg, SubprocessToParentMessage

class NotificationLevel:
    ''' 
    Notification level determines how an item is visualized on the frontend.

    Levels with the prefix 'APP' specify high-level state changes.
    '''
    APP_START           = 'app_start'
    APP_COMPLETE        = 'app_complete'
    APP_PAUSE           = 'app_pause'
    APP_RESUME          = 'app_resume'
    APP_STATE_CHANGE    = 'app_state_change'
    APP_ESTOP           = 'app_estop_set'
    APP_ESTOP_RELEASE   = 'app_estop_release'
    INFO                = 'info'
    WARNING             = 'warning'
    ERROR               = 'error'
    IO_STATE            = 'io_state'
    UI_INFO             = 'ui_info'

def sendNotification(level, message, customPayload=None):
    '''
        Broadcast a message to all connected clients

        params:
            level: str
                Notification level defines how the data is visualized on the client
            message: str
                message to be shown on the client
            customPayload: dict
                (Optional) Custom data to be sent to the client, if any
    '''
    sendSubprocessToParentMsg(SubprocessToParentMessage.NOTIFICATION, {
        "timeSeconds": time.time(),
        "level": level,
        "message": message,
        "customPayload": customPayload
    })


class Notifier:

    ''' 
    Websocket server used to stream information about a run in progress to the web client

    For internal use only! If you plan to send notifications 
    
    '''
    def __init__(self):
        self.__logger = logging.getLogger(__name__)
        self.lock = RLock()
        self.queue = []

        thread = Thread(name='Notifier', target=self.__run, args=('0.0.0.0', '8081'))
        thread.daemon = True
        thread.start() 

    def __run(self, ip, port):
        self.__logger.info('Running the socket API on port {}'.format(port))
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.server = websockets.serve(self.handler, ip, port)
        self.clients = set()
        
        asyncio.get_event_loop().create_task(self.run())
        asyncio.get_event_loop().run_until_complete(self.server)
        asyncio.get_event_loop().run_forever()

    async def handler(self, websocket, path):
        self.__logger.info('Received new client.')
        self.clients.add(websocket)
        try:
            while True:
                message = await websocket.recv()
                pass
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)

    async def run(self):
        self.isRunning = True
        while self.isRunning:
            sendQueue = []
            with self.lock:
                sendQueue = self.queue.copy()
                self.queue.clear()

            for item in sendQueue:
                jsonifiedMsg = json.dumps(item)
                try:
                    await asyncio.gather(
                        *[ws.send(jsonifiedMsg) for ws in self.clients],
                        return_exceptions=False
                    )
                except Exception as e:
                    self.__logger.error('Exception while trying to send data: {}'.format(str(e)))

            await asyncio.sleep(0.16)
        
        self.__logger.info('Websocket loop exiting.')
            
    def setDead(self):
        self.isRunning = False
        self.__logger.info('Websocket server set to die')

    def sendMessage(self, level, message, customPayload=None):
        '''
        Broadcast a message to all connected clients

        params:
            level: str
                Notification level defines how the data is visualized on the client
            message: str
                message to be shown on the client
            customPayload: dict
                (Optional) Custom data to be sent to the client, if any
        '''

        jsonMsg = {
            "timeSeconds": time.time(),
            "level": level,
            "message": message,
            "customPayload": customPayload
        }

        with self.lock:
            self.queue.append(jsonMsg)

globalNotifier = None

def initializeNotifier():
    global globalNotifier
    if globalNotifier != None:
        logging.error('Attempting to initialize the globalNotifier again')
        return
        
    globalNotifier = Notifier()

def getNotifier():
    ''' Retrieves the singleton instance of the global notifier '''
    global globalNotifier
    if globalNotifier == None:
        globalNotifier = Notifier()

    return globalNotifier