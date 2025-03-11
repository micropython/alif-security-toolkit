"""
 Serial ISP Communication port handling module

 default constructor
 openSerial
 closeSerial
 readSerial
 PrintStr
 DecodePacket
 checkSum

__author__ = "ronyett"
__copyright__ = "ALIF Seminconductor"
__version__ = "0.2.0"
__status__ = "Dev"    "

"""

# pylint: disable=unused-argument, invalid-name, bare-except
import sys
import time
import threading
import serial
from serial.tools import list_ports
from isp.isp_protocol import ISP_STATUS_READER_STOP, ISP_UNKNOWN_COMMAND, ISP_SUCCESS

# Serial defaults
COM_FILE_DEFAULT = "isp_config_data.cfg"
COM_PORT_DEFAULT = "COM3"
COM_BAUD_RATE_MAXIMUM = 921600
COM_TIMEOUT_RX_DEFAULT = 0.5
COM_TIMEOUT_TX_DEFAULT = 2.0


class serialPort:
    """
    serialPort
    Attributes
    """

    def __init__(self, baudRate):
        """
        constructor
        """
        self.serialData = serial.Serial()
        self.baudRate = baudRate
        self.portName = COM_PORT_DEFAULT
        self.portOverride = False
        self.timeOut = COM_TIMEOUT_RX_DEFAULT
        self.writeTimeout = COM_TIMEOUT_TX_DEFAULT
        """
           Related to ISP handling
        """
        self.verboseMode = False
        self.exit_on_nack = True
        self.last_command = ISP_UNKNOWN_COMMAND
        self.last_error = ISP_SUCCESS
        self.last_packet = []
        self.readerTask = None
        self.readerStatus = ISP_STATUS_READER_STOP
        self.readerLock = threading.Lock()
        self.eventFlag = threading.Event()
        self.readThread = threading.Event()
        self.eventFlag.clear()
        self.CTRLCHandler = None

    def getReaderStatus(self):
        """
        getReaderStatus
        return the reader status
        """
        return self.readerStatus

    def setReaderStatus(self, status):
        """
        setReaderStatus
        set the reader status
        """
        self.readerStatus = status

    def getPort(self):
        """
        getPort
        return name of the COM port
        """
        return self.serialData.port

    def setPort(self, com_port):
        """
        setPort
        """
        self.portName = com_port
        self.portOverride = True

    def setSerialFile(self, filename):
        """
        save serial information to a local file
        """
        try:
            fs = open(filename, "w")
        except IOError as e:
            print(f"[ERROR] setSerialFile {e}")
            sys.exit()
        with fs:
            fs.write(f"comport {self.portName}\n")
            fs.write(f"timeout tx {self.writeTimeout}\n")
            fs.write(f"timeout rx {self.timeOut}\n")
            fs.write(f"stopbits {self.serialData.stopbits}\n")
            fs.write(f"bytesize {self.serialData.bytesize}\n")
            fs.write(f"rtscts   {self.serialData.rtscts}\n")
            fs.write(f"xonxoff  {self.serialData.xonxoff}\n")
            #            fs.write('parity      %d\n'%self.serialData.parity)

            fs.close()

    def getSerialFile(self, filename):
        """
        open serial config file
        if file does not exist we raise an exception
        """
        portName = ""
        self.PrintStr("[DBG] getSerialFile - starts %s" % (filename))

        # test of the config file exists
        try:
            fs = open(filename, "r")
            self.PrintStr(f"[DBG] getSerialFile opened {filename}")
        except IOError as e:
            self.PrintStr("[INFO] getSerialFile - no config file}")
            raise
        else:
            with fs:
                alllines = fs.readlines()
                for oneline in alllines:
                    content = oneline.split(" ")
                    if len(content) == 2:
                        if content[0] == "comport":
                            portName = content[1].strip()

        self.portName = portName

        self.PrintStr(f"[DBG] getSerialFile baud {self.baudRate} port {self.portName}")

        return self.portName, self.baudRate

    def getVerbose(self):
        """
        getVerbose
        return the verbosity state
        """
        return self.verboseMode

    def setVerbose(self, verbose):
        """
        setVerbose
        set the verbosity mode
        """
        self.verboseMode = verbose

    def PrintStr(self, outputData):
        """
        PrintStr
        output data, for now using print()
        """
        #        if "DBG" not in outputData:
        if self.verboseMode or "ERROR" in outputData:
            if "DBG" not in outputData:
                print(outputData)

    def checkSum(self, checkBytes):
        """
        checksum calculation
        returns calculated checksum for addition to the message
        """
        checkByte = sum(checkBytes)
        inputType = type(checkBytes)
        checkSumByte = (((checkByte + 1) ^ 0xFF) + 2) & 0xFF

        return checkBytes + inputType([checkSumByte])

    def openSerial(self):
        """
        openSerial
        - Open the Serial port
        """
        self.PrintStr("[DBG] openSerial STARTS")

        # read config file - if it doesnt exist we can discover
        if self.portOverride:
            print(f"[INFO] port override {self.portName}")
        else:
            try:
                self.portName, self.baudRate = self.getSerialFile(COM_FILE_DEFAULT)
            except:
                self.discoverSerialPorts()

        self.serialData.port = self.portName
        self.serialData.baudrate = self.baudRate
        self.serialData.timeout = self.timeOut
        self.serialData.parity = serial.PARITY_NONE
        self.serialData.stopbits = serial.STOPBITS_ONE
        self.serialData.bytesize = serial.EIGHTBITS
        self.serialData.rtscts = False
        self.serialData.dsrdtr = False
        self.serialData.xonxoff = False

        self.PrintStr(f"[DBG] openSerial Baud rate {self.serialData.baudrate}")
        self.PrintStr(f"[DBG] openSerial COM port  {self.serialData.port}")

        try:
            self.PrintStr(f"[DBG] openSerial {self.serialData.port}")
            self.serialData.open()
        except serial.SerialException as e:
            self.PrintStr(f"[ERROR] openSerial {str(e)}")
            self.serialData.close()

            return False

        self.serialData.flushInput()
        self.serialData.flushOutput()

        self.PrintStr(f"[DBG] openSerial DONE {self.serialData.port}")

        return True

    def closeSerial(self):
        """
        closeSerial
        - Closes COM port
        """
        try:
            self.serialData.close()
            self.PrintStr(f"[INFO] {self.serialData.port} closeSerial success")

            ErrorCode = True
        except:
            self.PrintStr("[ERROR] {self.serialData.port} closeSerial failed")
            ErrorCode = False

        return ErrorCode

    def readSerial(self, numberBytes):
        """
        readSerial
        - Read number of bytes from the port
        """
        data = []
        try:
            data = self.serialData.read(numberBytes)
            if data != []:
                data = list(bytearray(data))
            self.PrintStr(f"[DBG] readSerial {len(data)} bytes ")
            self.PrintStr(f"[DBG] {data}")
        except serial.SerialException as e:
            self.PrintStr(
                f"[ERROR] {self.serialData.port} readSerial reporting disconnected"
            )

            # Reset the Terminal of any ANSI Escape sequence debris
            print("\033[0m")
            print("\033[?25h")  # Cursor reenables
            sys.exit(
                1
            )  # cable is disconnected, exit so user reconnects and runs the tool again
            # return []

        return data

    def writeSerial(self, bytetoWrite):
        """
        writeSerial
        - write byte(s) to the port
        """
        try:
            sent = self.serialData.write(bytearray(bytetoWrite))
            self.serialData.flush()
            self.PrintStr(f"[DBG] writeSerial sent {sent}")
            return True
        except serial.SerialTimeoutException:
            self.PrintStr(f"[ERROR] {self.serialData.port} writeSerial Timeout")
            return False
        except serial.SerialException as e:
            self.PrintStr(f"[ERROR] {self.serialData.port} writeSerial write failed")
            print(e)
            self.serialData.flushOutput()
            return False

        return True

    def setBaudRate(self, new_baud_rate):
        """setBaudRate

        Args:
          self
          new_naud_rate
        """
        self.serialData.baudrate = new_baud_rate
        time.sleep(1)
        self.serialData.flush()
        self.serialData.flushInput()
        self.serialData.flushOutput()

    def getBaudRate(self):
        """getBadrate

        Args:
           self
        """
        return self.serialData.baudrate

    def setTimeout(self, new_timeout):
        """setTimeout

        Args:
           self
           new_timeout
        """
        self.serialData.timeout = new_timeout

    def getTimeout(self):
        """getTimeout

        Args:
           self
        """
        return self.serialData.timeout

    def discoverSerialPorts(self):
        """
        DiscoverSerialPorts
        - Obtain the available COM ports
        """
        try:
            from serial.tools.list_ports import comports
        except ImportError:
            return None

        AvailablePorts = list_ports.comports()

        if not AvailablePorts:
            self.PrintStr("[ERROR] Cannot found active COM port")
            return False

        #        self.PrintStr("COM ports detected = %d" %len(AvailablePorts))
        print(f"COM ports detected = {len(AvailablePorts)}")

        for comPorts in AvailablePorts:
            print("-> {:20}".format(comPorts.device))

        try:
            PortName = input("Enter port name:")
        except EOFError:
            print(" Operation cancelled by the user!")
            print("")
            sys.exit(0)

        if PortName == "":
            PortName = comPorts.device

        self.serialData.port = PortName
        self.portName = PortName

        ErrorCode = False
        for PortInfo in AvailablePorts:
            if PortInfo.device == self.serialData.port:
                ErrorCode = True
                break

        if ErrorCode is True:
            self.PrintStr(f"[DBG] Port Name {self.serialData.port}")
        else:
            self.PrintStr(f"[ERROR] {self.serialData.port} is not a valid port name")

        self.setSerialFile(COM_FILE_DEFAULT)

        return True

    def showSerial(self):
        """
        showSerial
        - dump infomation regarding the COM port
        """


if __name__ == "__main__":
    print("*** Serial port test harness ***")

    isp = serialPort(57600)
    isp.discoverSerialPorts()
    isp.openSerial()

    isp.closeSerial()
