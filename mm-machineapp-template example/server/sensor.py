import logging
log = logging.getLogger(__name__)
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as MQTTsubscribe
import time

class Sensor():
    _on_rising_edge_flag = False
    _on_falling_edge_flag = False
    
    _on_rising_edge_cb = None
    _on_falling_edge_cb = None
    _on_state_change_cb = None
    
    class timeoutException(Exception):
        pass

    def getState(self):
        return self.state
        
    def __onConnect(self, client, userData, flags, rc):
        if rc == 0:
            self.mqtt_topic = 'devices/io-expander/'+ str(self.networkId) +'/digital-input/'+ str(self.pin)
            self.sensorClient.subscribe(self.mqtt_topic)
            self.connected=True
            log.info(self.name + " connected to pin " + str(self.pin))
        

    def __onMessage(self, client, userData, msg):
        print("{} received msg {}".format(self.name, msg.payload))
        value = msg.payload
        self.state = int(value)
        ret = ""
        
        
        if not self.has_received_first_message:
            return
        
        if self.state == 1:
            self._on_rising_edge_flag = True
            if self._on_rising_edge_cb is not None:
                ret = self._on_rising_edge_cb()
        elif self.state ==0:
            self._on_falling_edge_flag = True
            if self._on_falling_edge_cb is not None:
                ret = self._on_falling_edge_cb()
        elif self._on_state_change_cb is not None:
            ret = self._on_state_change_cb()
        return ret
        
        

    def __init__(self, name, ipAddress, networkId, pin):
        self.connected=False
        self.networkId = networkId
        self.pin = pin
        self.name = name
        self.sensorClient = None
        self.sensorClient = mqtt.Client()
        self.sensorClient.on_connect = self.__onConnect
        self.sensorClient.on_message = self.__onMessage
        self.sensorClient.connect(ipAddress)
        self.has_received_first_message = False
        self.sensorClient.loop_start()
        
        t0 = time.time()
        connection_timeout = 5 #timeout after 5 seconds
        while self.connected==False:
            if time.time()-t0 > connection_timeout:
                raise self.timeoutException("system timeout during connection to to {}".format(self.name))
                
            time.sleep(0.2)

    
    def register_on_rising_edge(self, cb):
        self._on_rising_edge_cb = cb
    def register_on_falling_edge(self, cb):
        self._on_falling_edge_cb = cb
    def register_on_value_change(self, cb):
        self._on_state_change_cb = cb
        
    #Returns true after rising edge has been detected
    def wait_for_rising_edge(self, timeout = None):
        print("{} waiting for rising edge\n\t{}".format(self.name, self.mqtt_topic))
        #Wait for the rising edge flag to trigger True. 
        t0 = time.time()
        while self._on_rising_edge_flag == False:
            if timeout is not None and time.time()-t0 > timeout:
                raise self.timeoutException("system timeout wait_for_rising_edge {}".format(self.name))
            time.sleep(0.5)
        self._on_rising_edge_flag = False
        return
    
    def wait_for_falling_edge(self, timeout = None):
        #Wait for the rising edge flag to trigger True. 
        t0 = time.time()
        while self._on_falling_edge_flag == False:
            if timeout is not None and time.time()-t0 > timeout:
                raise Exception("system timeout wait_for_falling_edge {}".format(self.name))
            time.sleep(0.5)
        self._on_falling_edge_flag = False
        return
    
    def seen_rising_edge(self):
        if self._on_rising_edge_flag:
            self._on_rising_edge_flag = False
            return True
        return False

    def seen_falling_edge(self):
        if self._on_falling_edge_flag:
            self._on_falling_edge_flag = False
            return True
        return False

# example code
if __name__ == '__main__':
    test_sensor1 = Sensor("Test Sensor1", ipAddress="192.168.7.2", networkId=1, pin=1)
    test_sensor2 = Sensor("Test Sensor2", ipAddress="192.168.7.2", networkId=1, pin=2)
    test_sensor3 = Sensor("Test Sensor3", ipAddress="192.168.7.2", networkId=1, pin=3)
    
    try:
        # test_sensor1.wait_for_rising_edge(5)
        test_sensor2.wait_for_rising_edge(2)
        test_sensor3.wait_for_rising_edge(5)
    except Sensor.timeoutException:
        print("Sensor timeout")
