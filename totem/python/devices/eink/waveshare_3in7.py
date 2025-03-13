import os
import sys
import time
import logging
import traceback
from PIL import Image, ImageDraw, ImageFont

try:
    import lgpio
    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False
    logging.warning("lgpio not available, e-ink display will not work in hardware mode")

# Import RPi.GPIO if lgpio not available (for older Raspberry Pi)
if not LGPIO_AVAILABLE:
    try:
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        # Use BCM pin numbering
        GPIO.setmode(GPIO.BCM)
    except ImportError:
        GPIO_AVAILABLE = False
        logging.warning("Neither lgpio nor RPi.GPIO available, e-ink display will not work in hardware mode")

# Constants for the waveshare 3.7inch e-paper display
PANEL_SETTING = 0x00
POWER_SETTING = 0x01
POWER_OFF = 0x02
POWER_OFF_SEQUENCE_SETTING = 0x03
POWER_ON = 0x04
POWER_ON_MEASURE = 0x05
BOOSTER_SOFT_START = 0x06
DEEP_SLEEP = 0x07
DATA_START_TRANSMISSION_1 = 0x10
DATA_STOP = 0x11
DISPLAY_REFRESH = 0x12
DATA_START_TRANSMISSION_2 = 0x13
LUT_FOR_VCOM = 0x20
LUT_WHITE_TO_WHITE = 0x21
LUT_BLACK_TO_WHITE = 0x22
LUT_WHITE_TO_BLACK = 0x23
LUT_BLACK_TO_BLACK = 0x24
PLL_CONTROL = 0x30
TEMPERATURE_SENSOR_COMMAND = 0x40
TEMPERATURE_SENSOR_SELECTION = 0x41
TEMPERATURE_SENSOR_WRITE = 0x42
TEMPERATURE_SENSOR_READ = 0x43
TEMPERATURE_SENSOR_CALIBRATION = 0x40  # Same as TEMPERATURE_SENSOR_COMMAND
VCOM_AND_DATA_INTERVAL_SETTING = 0x50
LOW_POWER_DETECTION = 0x51
TCON_SETTING = 0x60
RESOLUTION_SETTING = 0x61
GSST_SETTING = 0x65
GET_STATUS = 0x71
AUTO_MEASUREMENT_VCOM = 0x80
READ_VCOM_VALUE = 0x81
VCM_DC_SETTING = 0x82
PARTIAL_WINDOW = 0x90
PARTIAL_IN = 0x91
PARTIAL_OUT = 0x92
PROGRAM_MODE = 0xA0
ACTIVE_PROGRAMMING = 0xA1
READ_OTP = 0xA2
POWER_SAVING = 0xE3

# Pin definitions (Waveshare 3.7inch e-Paper HAT)
# These pins can be overridden by environment variables:
# - USE_ALT_EINK_PINS=1 to enable using alternative pins
# - EINK_RST_PIN, EINK_DC_PIN, EINK_CS_PIN, EINK_BUSY_PIN to set specific pins
# - USE_SW_SPI=1 to use software SPI instead of hardware SPI
# - EINK_MOSI_PIN, EINK_SCK_PIN for software SPI pins
# - NVME_COMPATIBLE=1 to use pins that don't conflict with NVME hat
RST_PIN = int(os.environ.get('EINK_RST_PIN', 17)) if os.environ.get('USE_ALT_EINK_PINS') else 17
DC_PIN = int(os.environ.get('EINK_DC_PIN', 25)) if os.environ.get('USE_ALT_EINK_PINS') else 25
CS_PIN = int(os.environ.get('EINK_CS_PIN', 9)) if os.environ.get('USE_ALT_EINK_PINS') else 8
BUSY_PIN = int(os.environ.get('EINK_BUSY_PIN', 24)) if os.environ.get('USE_ALT_EINK_PINS') else 24

# Software SPI pins (only used if USE_SW_SPI=1)
MOSI_PIN = int(os.environ.get('EINK_MOSI_PIN', 10))  # GPIO 10 = MOSI
SCK_PIN = int(os.environ.get('EINK_SCK_PIN', 11))    # GPIO 11 = SCK

# Flag to use software SPI
USE_SW_SPI = os.environ.get('USE_SW_SPI', '0') == '1' or os.environ.get('NVME_COMPATIBLE', '0') == '1'

# Flag for NVME compatibility (uses alternative pins and software SPI)
NVME_COMPATIBLE = os.environ.get('NVME_COMPATIBLE', '0') == '1'

# If NVME_COMPATIBLE is set, override pins to avoid SPI conflicts
if NVME_COMPATIBLE:
    # Use pins that don't conflict with SPI0 or SPI1
    RST_PIN = int(os.environ.get('EINK_RST_PIN', 17))
    DC_PIN = int(os.environ.get('EINK_DC_PIN', 25))
    CS_PIN = int(os.environ.get('EINK_CS_PIN', 9))
    BUSY_PIN = int(os.environ.get('EINK_BUSY_PIN', 24))
    MOSI_PIN = int(os.environ.get('EINK_MOSI_PIN', 22))  # Use non-SPI pin
    SCK_PIN = int(os.environ.get('EINK_SCK_PIN', 23))    # Use non-SPI pin
    USE_SW_SPI = True

# Display resolution
EPD_WIDTH = 280
EPD_HEIGHT = 480

# Potentially conflicting pins to check
CONFLICTING_PINS = [RST_PIN, DC_PIN, BUSY_PIN, CS_PIN]

class GPIOError(Exception):
    """Error related to GPIO access"""
    pass

class WaveshareEPD3in7:
    """Waveshare 3.7inch e-Paper HAT driver"""
    
    def __init__(self):
        """Initialize the driver"""
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.spi = None
        self.gpio_handle = None
        self.pin_handles = {}
        self.lut_vcom0 = None  # Will be set during init
        self.lut_ww = None     # Will be set during init
        self.lut_bw = None     # Will be set during init
        self.lut_wb = None     # Will be set during init
        self.lut_bb = None     # Will be set during init
        self.initialized = False
        self.mock_mode = os.environ.get('EINK_MOCK_MODE', '0') == '1'
        self.using_rpi_gpio = False
        self.using_sw_spi = USE_SW_SPI
        self.nvme_compatible = NVME_COMPATIBLE
        self.hardware_type = self._detect_hardware()
        self.handle_errors = os.environ.get('EINK_HANDLE_ERRORS', '1') == '1'
        self.busy_timeout = int(os.environ.get('EINK_BUSY_TIMEOUT', 10))  # Timeout in seconds for busy pin
        
        if self.nvme_compatible:
            print("Running in NVME-compatible mode with software SPI")
            print(f"Using pins: RST={RST_PIN}, DC={DC_PIN}, CS={CS_PIN}, BUSY={BUSY_PIN}")
            print(f"Software SPI pins: MOSI={MOSI_PIN}, SCK={SCK_PIN}")
        
    def _detect_hardware(self):
        """
        Detect which hardware we're running on
        Returns:
            str: Type of hardware ('pi5', 'pi4', 'other', 'unknown')
        """
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi 5' in model:
                    print("Detected Raspberry Pi 5")
                    return 'pi5'
                elif 'Raspberry Pi 4' in model:
                    print("Detected Raspberry Pi 4")
                    return 'pi4'
                else:
                    print(f"Detected other Raspberry Pi: {model}")
                    return 'other'
        except:
            print("Could not detect hardware type")
            return 'unknown'
    
    def _check_conflicting_gpio_usage(self):
        """
        Check if any of our GPIO pins are already in use
        
        Returns:
            tuple: (list of busy pins, list of processes using them)
        """
        busy_pins = []
        processes = []
        
        try:
            import subprocess
            result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # More than just the header line
                    processes = [line.split()[1] for line in lines[1:]]  # Get PIDs
                    busy_pins = CONFLICTING_PINS  # Assume all pins might be in conflict
                    # We don't know exactly which pins are used by which process
                    # This is a conservative approach
            
            return busy_pins, processes
        except Exception as e:
            print(f"Error checking GPIO usage: {e}")
            return [], []
    
    def _can_acquire_gpio(self):
        """Check if we can acquire the GPIO pins we need"""
        # If we can open the pins, we can acquire them
        if not LGPIO_AVAILABLE and not GPIO_AVAILABLE:
            return False
            
        busy_pins, processes = self._check_conflicting_gpio_usage()
        if busy_pins:
            print(f"Warning: GPIO pins may be in use by processes: {', '.join(processes)}")
            return False
            
        return True
    
    def _setup_gpio_and_spi(self):
        """Set up GPIO and SPI interfaces"""
        if not LGPIO_AVAILABLE and not GPIO_AVAILABLE:
            raise GPIOError("Neither lgpio nor RPi.GPIO available")
        
        # Check permissions and device access
        if not os.path.exists('/dev/gpiochip0'):
            raise GPIOError("GPIO device not available: /dev/gpiochip0")
            
        # Only check SPI device if not using software SPI
        if not self.using_sw_spi:
            if not os.path.exists('/dev/spidev0.0'):
                if self.handle_errors:
                    print("SPI device not available, falling back to software SPI")
                    self.using_sw_spi = True
                else:
                    raise GPIOError("SPI device not available: /dev/spidev0.0")
                
            # Check permissions
            elif not os.access('/dev/spidev0.0', os.R_OK | os.W_OK):
                if self.handle_errors:
                    print("No permission to access SPI device, falling back to software SPI")
                    self.using_sw_spi = True
                else:
                    raise GPIOError("No permission to access /dev/spidev0.0")
        
        # Check permissions for GPIO
        if not os.access('/dev/gpiochip0', os.R_OK | os.W_OK):
            raise GPIOError("No permission to access /dev/gpiochip0")
        
        try:
            # Check if GPIO pins are already in use
            busy_pins, processes = self._check_conflicting_gpio_usage()
            if busy_pins and processes:
                print(f"Warning: GPIO pins {busy_pins} may be in use by processes: {', '.join(processes)}")
                
                # If NVME_COMPATIBLE mode is enabled, we try to use pins that don't conflict
                if self.nvme_compatible:
                    print("NVME compatibility mode enabled, using alternative pins")
                    # Pins have already been set at module level
                else:
                    print("Consider setting NVME_COMPATIBLE=1 to use non-conflicting pins")
            
            # For Raspberry Pi 5, we use lgpio
            if self.hardware_type in ['pi5', 'pi4'] and LGPIO_AVAILABLE:
                print(f"Using Pi {self.hardware_type} compatible GPIO (gpiod)")
                self.gpio_handle = lgpio.gpiochip_open(0)
                
                # Try to claim GPIO pins, with better error handling
                pins_to_configure = [RST_PIN, DC_PIN, CS_PIN]
                if self.using_sw_spi:
                    pins_to_configure.extend([MOSI_PIN, SCK_PIN])
                
                for pin in pins_to_configure:
                    try:
                        handle = lgpio.gpio_claim_output(self.gpio_handle, pin, 0)
                        self.pin_handles[pin] = handle
                    except Exception as e:
                        if self.handle_errors:
                            print(f"Error claiming pin {pin}: {e}")
                            print(f"Try setting NVME_COMPATIBLE=1 or manually specify an alternative pin")
                            self.mock_mode = True
                            return
                        else:
                            raise GPIOError(f"Could not claim GPIO pin {pin}: {e}")
                
                # Configure BUSY pin as input
                try:
                    handle = lgpio.gpio_claim_input(self.gpio_handle, BUSY_PIN)
                    self.pin_handles[BUSY_PIN] = handle
                except Exception as e:
                    if self.handle_errors:
                        print(f"Error claiming BUSY pin {BUSY_PIN}: {e}")
                        self.mock_mode = True
                        return
                    else:
                        raise GPIOError(f"Could not claim BUSY pin {BUSY_PIN}: {e}")
                
                # If using software SPI, set up MOSI and SCK pins
                if self.using_sw_spi:
                    print(f"Using software SPI with MOSI={MOSI_PIN}, SCK={SCK_PIN}")
                    self.spi = None  # No hardware SPI
                else:
                    # Open SPI device
                    try:
                        self.spi = lgpio.spi_open(0, 0, 10000000, 0)  # 10MHz, mode 0
                        print("Hardware SPI initialized with lgpio")
                    except Exception as e:
                        print(f"Error opening SPI device: {e}")
                        if self.handle_errors:
                            print("Falling back to software SPI")
                            self.using_sw_spi = True
                            self.spi = None
                            # Need to claim MOSI and SCK pins for software SPI
                            for pin in [MOSI_PIN, SCK_PIN]:
                                try:
                                    handle = lgpio.gpio_claim_output(self.gpio_handle, pin, 0)
                                    self.pin_handles[pin] = handle
                                except:
                                    print(f"Could not claim pin {pin} for software SPI")
                                    self.mock_mode = True
                                    return
                        else:
                            raise GPIOError(f"Could not open SPI device: {e}")
                
            # For other Raspberry Pi, use RPi.GPIO
            elif GPIO_AVAILABLE:
                print("Using RPi.GPIO for GPIO access")
                # Set up GPIO pins
                GPIO.setwarnings(False)  # Disable warnings about pins already in use
                
                # Set up GPIO pins with better error handling
                pins_to_configure = {
                    RST_PIN: GPIO.OUT,
                    DC_PIN: GPIO.OUT,
                    CS_PIN: GPIO.OUT,
                    BUSY_PIN: GPIO.IN
                }
                
                # Add SPI pins if using software SPI
                if self.using_sw_spi:
                    pins_to_configure[MOSI_PIN] = GPIO.OUT
                    pins_to_configure[SCK_PIN] = GPIO.OUT
                
                for pin, direction in pins_to_configure.items():
                    try:
                        GPIO.setup(pin, direction)
                    except Exception as e:
                        if self.handle_errors:
                            print(f"Error setting up pin {pin}: {e}")
                            self.mock_mode = True
                            return
                        else:
                            raise GPIOError(f"Could not set up GPIO pin {pin}: {e}")
                
                # Set up hardware SPI if not using software SPI
                if not self.using_sw_spi:
                    try:
                        # Initialize SPI using spidev
                        import spidev
                        self.spi = spidev.SpiDev()
                        self.spi.open(0, 0)
                        self.spi.max_speed_hz = 10000000  # 10MHz
                        self.spi.mode = 0
                        print("Hardware SPI initialized with spidev")
                    except Exception as e:
                        print(f"Error initializing hardware SPI: {e}")
                        if self.handle_errors:
                            print("Falling back to software SPI")
                            self.using_sw_spi = True
                            self.spi = None
                        else:
                            raise GPIOError(f"Could not initialize SPI: {e}")
                else:
                    print(f"Using software SPI with MOSI={MOSI_PIN}, SCK={SCK_PIN}")
                    self.spi = None
                
                self.using_rpi_gpio = True
                
            else:
                raise GPIOError("No suitable GPIO/SPI library available")
                
        except Exception as e:
            error_msg = f"Error setting up GPIO/SPI: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            # Clean up any partially initialized resources
            self.close()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise GPIOError(error_msg)
    
    def init(self):
        """Initialize the e-Paper display"""
        if self.initialized:
            return
            
        try:
            # Try to set up GPIO and SPI
            self._setup_gpio_and_spi()
            
            # Proceed with display initialization
            self.reset()
            
            self.send_command(POWER_SETTING)
            self.send_data(0x37)
            self.send_data(0x00)
            
            self.send_command(PANEL_SETTING)
            self.send_data(0xCF)
            self.send_data(0x08)
            
            self.send_command(BOOSTER_SOFT_START)
            self.send_data(0xc7)
            self.send_data(0xcc)
            self.send_data(0x28)
            
            self.send_command(POWER_ON)
            self.wait_until_idle()
            
            self.send_command(PLL_CONTROL)
            self.send_data(0x3c)
            
            self.send_command(TEMPERATURE_SENSOR_CALIBRATION)
            self.send_data(0x00)
            
            self.send_command(VCOM_AND_DATA_INTERVAL_SETTING)
            self.send_data(0x77)
            
            self.send_command(TCON_SETTING)
            self.send_data(0x22)
            
            self.send_command(RESOLUTION_SETTING)
            self.send_data(0x01)  # width: 280
            self.send_data(0x18)
            self.send_data(0x01)  # height: 480
            self.send_data(0xe0)
            
            self.send_command(VCM_DC_SETTING)
            self.send_data(0x1E)  # decide by LUT file
            
            self.send_command(0xe5)  # FLASH MODE
            self.send_data(0x03)
            
            # LUT setting
            self.set_lut()
            
            self.initialized = True
            
        except Exception as e:
            error_msg = f"Error initializing display: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            # Clean up any partially initialized resources
            self.close()
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode")
                self.mock_mode = True
                self.initialized = True
            else:
                raise RuntimeError(error_msg)
    
    def reset(self):
        """Reset the display"""
        if self.mock_mode:
            print("Mock reset")
            return
            
        try:
            self._digital_write(RST_PIN, 1)
            time.sleep(0.2)
            self._digital_write(RST_PIN, 0)
            time.sleep(0.2)
            self._digital_write(RST_PIN, 1)
            time.sleep(0.2)
        except Exception as e:
            error_msg = f"Error resetting display: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode during reset")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def _digital_write(self, pin, value):
        """Write to a GPIO pin"""
        if self.mock_mode:
            print(f"Mock digital write: pin={pin}, value={value}")
            return
            
        try:
            if self.using_rpi_gpio:
                GPIO.output(pin, value)
            else:
                lgpio.gpio_write(self.gpio_handle, pin, value)
        except Exception as e:
            error_msg = f"Error writing to GPIO pin {pin}: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after GPIO error")
                self.mock_mode = True
            else:
                raise GPIOError(error_msg)
    
    def _digital_read(self, pin):
        """Read from a GPIO pin"""
        if self.mock_mode:
            print(f"Mock digital read: pin={pin}")
            return 1  # Always return "not busy" in mock mode
            
        try:
            if self.using_rpi_gpio:
                return GPIO.input(pin)
            else:
                return lgpio.gpio_read(self.gpio_handle, pin)
        except Exception as e:
            error_msg = f"Error reading from GPIO pin {pin}: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after GPIO error")
                self.mock_mode = True
                return 1  # Return "not busy"
            else:
                raise GPIOError(error_msg)
    
    def _spi_transfer(self, data):
        """Transfer data over SPI (hardware or software)"""
        if self.mock_mode:
            return [0] * len(data) if isinstance(data, list) else 0
            
        if self.using_sw_spi:
            return self._sw_spi_transfer(data)
        else:
            # Hardware SPI
            if self.using_rpi_gpio:
                return self.spi.xfer2(data if isinstance(data, list) else [data])
            else:
                # lgpio SPI
                return lgpio.spi_xfer(self.spi, data if isinstance(data, list) else [data])[1]
    
    def _sw_spi_transfer(self, data):
        """Software SPI implementation"""
        if not isinstance(data, list):
            data = [data]
            
        result = []
        
        for byte in data:
            result_byte = 0
            
            # Transfer one byte, MSB first
            for i in range(8):
                bit = (byte >> (7-i)) & 0x01
                
                # Set MOSI pin
                if self.using_rpi_gpio:
                    GPIO.output(MOSI_PIN, bit)
                else:
                    lgpio.gpio_write(self.gpio_handle, MOSI_PIN, bit)
                
                # Pulse clock
                if self.using_rpi_gpio:
                    GPIO.output(SCK_PIN, 1)
                    time.sleep(0.00001)  # 10µs delay
                    GPIO.output(SCK_PIN, 0)
                else:
                    lgpio.gpio_write(self.gpio_handle, SCK_PIN, 1)
                    time.sleep(0.00001)  # 10µs delay
                    lgpio.gpio_write(self.gpio_handle, SCK_PIN, 0)
                
                # We're not reading data back in this implementation
                
            result.append(0)  # We're not reading data back
            
        return result
    
    def send_command(self, command):
        """Send command to the display"""
        if self.mock_mode:
            print(f"Mock send command: {command:#x}")
            return
            
        try:
            # Set DC pin to command mode (low)
            self._digital_write(DC_PIN, 0)
            
            # Set CS pin low to select the display
            self._digital_write(CS_PIN, 0)
            
            # Send the command byte
            self._spi_transfer(command)
            
            # Set CS pin high to deselect the display
            self._digital_write(CS_PIN, 1)
        except Exception as e:
            print(f"Error sending command: {e}")
            if self.handle_errors:
                self.mock_mode = True
                print(f"Mock send command: {command:#x}")
            else:
                raise
    
    def send_data(self, data):
        """Send data to the display"""
        if self.mock_mode:
            if isinstance(data, list) and len(data) > 10:
                print(f"Mock send data: {len(data)} bytes")
            else:
                print(f"Mock send data: {data}")
            return
            
        try:
            # Set DC pin to data mode (high)
            self._digital_write(DC_PIN, 1)
            
            # Set CS pin low to select the display
            self._digital_write(CS_PIN, 0)
            
            # Send the data
            self._spi_transfer(data)
            
            # Set CS pin high to deselect the display
            self._digital_write(CS_PIN, 1)
        except Exception as e:
            print(f"Error sending data: {e}")
            if self.handle_errors:
                self.mock_mode = True
                if isinstance(data, list) and len(data) > 10:
                    print(f"Mock send data: {len(data)} bytes")
                else:
                    print(f"Mock send data: {data}")
            else:
                raise
    
    def wait_until_idle(self, timeout=None, debug_level=logging.INFO):
        """Wait until the display is idle (not busy)"""
        if timeout is None:
            timeout = self.busy_timeout
            
        if self.mock_mode:
            print("Mock wait until idle")
            time.sleep(0.1)  # Simulate a short delay
            return
            
        try:
            # Wait for busy pin to be high (not busy)
            print("Waiting for display to be ready...")
            logging.log(debug_level, f"Waiting for BUSY_PIN ({BUSY_PIN}) to go high...")
            
            # First, verify we can read the busy pin
            try:
                busy_state = self._digital_read(BUSY_PIN)
                logging.log(debug_level, f"Initial BUSY_PIN state: {busy_state}")
            except Exception as e:
                logging.error(f"Error reading BUSY_PIN: {e}")
                if self.handle_errors:
                    print("Falling back to mock mode due to BUSY_PIN read error")
                    self.mock_mode = True
                    return
                else:
                    raise
            
            # Now wait for it to change
            start_time = time.time()
            poll_count = 0
            timeout_occurred = False
            
            while self._digital_read(BUSY_PIN) == 0:
                time.sleep(0.1)
                poll_count += 1
                
                # Log progress periodically
                if poll_count % 10 == 0:
                    elapsed = time.time() - start_time
                    logging.log(debug_level, f"Still waiting after {elapsed:.1f}s, poll count: {poll_count}")
                
                if time.time() - start_time > timeout:
                    timeout_occurred = True
                    print(f"Warning: Busy timeout after {timeout} seconds, continuing anyway")
                    logging.warning(f"BUSY_PIN timeout after {timeout}s and {poll_count} polls")
                    break
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            if timeout_occurred:
                logging.warning(f"BUSY timeout occurred after {elapsed:.1f}s")
            else:
                logging.log(debug_level, f"BUSY wait completed after {elapsed:.1f}s and {poll_count} polls")
                print("Display is now ready")
        except Exception as e:
            error_msg = f"Error waiting for display: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after wait error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def set_lut(self):
        """Set the look-up tables for the display"""
        if self.mock_mode:
            print("Mock set LUT")
            return
            
        try:
            self.lut_vcom0 = [
                0x00, 0x17, 0x00, 0x00, 0x00, 0x02,
                0x00, 0x17, 0x17, 0x00, 0x00, 0x02,
                0x00, 0x0A, 0x01, 0x00, 0x00, 0x01,
                0x00, 0x0E, 0x0E, 0x00, 0x00, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00,
            ]
            
            self.lut_ww = [
                0x40, 0x17, 0x00, 0x00, 0x00, 0x02,
                0x90, 0x17, 0x17, 0x00, 0x00, 0x02,
                0x40, 0x0A, 0x01, 0x00, 0x00, 0x01,
                0xA0, 0x0E, 0x0E, 0x00, 0x00, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
            
            self.lut_bw = [
                0x40, 0x17, 0x00, 0x00, 0x00, 0x02,
                0x90, 0x17, 0x17, 0x00, 0x00, 0x02,
                0x40, 0x0A, 0x01, 0x00, 0x00, 0x01,
                0xA0, 0x0E, 0x0E, 0x00, 0x00, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
            
            self.lut_wb = [
                0x80, 0x17, 0x00, 0x00, 0x00, 0x02,
                0x90, 0x17, 0x17, 0x00, 0x00, 0x02,
                0x80, 0x0A, 0x01, 0x00, 0x00, 0x01,
                0x50, 0x0E, 0x0E, 0x00, 0x00, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
            
            self.lut_bb = [
                0x80, 0x17, 0x00, 0x00, 0x00, 0x02,
                0x90, 0x17, 0x17, 0x00, 0x00, 0x02,
                0x80, 0x0A, 0x01, 0x00, 0x00, 0x01,
                0x50, 0x0E, 0x0E, 0x00, 0x00, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
            
            # Send the LUT to the display
            self.send_command(LUT_FOR_VCOM)
            for i in range(0, 44):
                self.send_data(self.lut_vcom0[i])
                
            self.send_command(LUT_WHITE_TO_WHITE)
            for i in range(0, 42):
                self.send_data(self.lut_ww[i])
                
            self.send_command(LUT_BLACK_TO_WHITE)
            for i in range(0, 42):
                self.send_data(self.lut_bw[i])
                
            self.send_command(LUT_WHITE_TO_BLACK)
            for i in range(0, 42):
                self.send_data(self.lut_wb[i])
                
            self.send_command(LUT_BLACK_TO_BLACK)
            for i in range(0, 42):
                self.send_data(self.lut_bb[i])
        except Exception as e:
            error_msg = f"Error setting LUT: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after LUT error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def Clear(self):
        """Clear the display"""
        if not self.initialized:
            self.init()
            
        if self.mock_mode:
            print("Mock clear display")
            return
            
        try:
            self.send_command(DATA_START_TRANSMISSION_1)
            for i in range(0, int(self.width * self.height / 8)):
                self.send_data(0xFF)
            
            self.send_command(DATA_START_TRANSMISSION_2)
            for i in range(0, int(self.width * self.height / 8)):
                self.send_data(0xFF)
                
            self.send_command(DISPLAY_REFRESH)
            self.wait_until_idle()
        except Exception as e:
            error_msg = f"Error clearing display: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after clear error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def display(self, image):
        """Display an image on the e-Paper display"""
        if not self.initialized:
            self.init()
            
        if self.mock_mode:
            print("Mock display image")
            return
            
        try:
            if image is None:
                return
                
            # Convert image to 1-bit black and white
            image_1bit = image.convert('1')
            
            # Send image data to display
            buf_black = bytearray(int(self.width * self.height / 8))
            buf_red = bytearray(int(self.width * self.height / 8))
            
            # Convert image to buffer
            image_black = image_1bit.load()
            for y in range(self.height):
                for x in range(self.width):
                    # Set the bits for black pixels
                    if image_black[x, y] == 0:  # Black
                        buf_black[int((x + y * self.width) / 8)] &= ~(0x80 >> (x % 8))
                    else:  # White
                        buf_black[int((x + y * self.width) / 8)] |= 0x80 >> (x % 8)
            
            # Send black buffer
            self.send_command(DATA_START_TRANSMISSION_1)
            for i in range(0, int(self.width * self.height / 8)):
                self.send_data(buf_black[i])
                
            # Send red buffer (same as black for b/w display)
            self.send_command(DATA_START_TRANSMISSION_2)
            for i in range(0, int(self.width * self.height / 8)):
                self.send_data(buf_red[i])
                
            # Refresh display
            self.send_command(DISPLAY_REFRESH)
            self.wait_until_idle()
        except Exception as e:
            error_msg = f"Error displaying image: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after display error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def display_text(self, text, x=10, y=10, font_size=24):
        """Display text on the e-Paper display"""
        if not self.initialized:
            self.init()
            
        if self.mock_mode:
            print(f"Mock display text: '{text}' at ({x},{y}) with font size {font_size}")
            return
            
        try:
            # Create a blank image
            image = Image.new('1', (self.width, self.height), 255)
            draw = ImageDraw.Draw(image)
            
            # Try to load a font from various paths
            font = None
            font_paths = [
                # Try project fonts directory
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                           'resources', 'fonts', 'FreeSans.ttf'),
                # Try common system font paths
                '/usr/share/fonts/truetype/freefont/FreeSans.ttf',  # Debian/Ubuntu
                '/usr/share/fonts/TTF/DejaVuSans.ttf',              # Arch Linux
                '/usr/share/fonts/dejavu/DejaVuSans.ttf',           # Fedora/RHEL
                '/System/Library/Fonts/Helvetica.ttc',               # macOS
                'C:\\Windows\\Fonts\\Arial.ttf'                      # Windows
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        print(f"Using font from: {font_path}")
                        break
                    except Exception as e:
                        print(f"Error loading font from {font_path}: {e}")
            
            if font is None:
                print("No TrueType fonts found, using default")
                font = ImageFont.load_default()
            
            # Draw the text
            draw.text((x, y), text, font=font, fill=0)
            
            # Display the image
            self.display(image)
        except Exception as e:
            error_msg = f"Error displaying text: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after text error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def sleep(self):
        """Put the display to sleep to conserve power"""
        if not self.initialized:
            return
            
        if self.mock_mode:
            print("Mock sleep")
            return
            
        try:
            self.send_command(POWER_OFF)
            self.wait_until_idle()
            self.send_command(DEEP_SLEEP)
            self.send_data(0xA5)  # Check code
        except Exception as e:
            error_msg = f"Error putting display to sleep: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after sleep error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def close(self):
        """Close the display and free resources"""
        if self.mock_mode:
            print("Mock close")
            self.initialized = False
            return
            
        try:
            # Close SPI
            if self.spi is not None:
                if self.using_rpi_gpio:
                    self.spi.close()
                else:
                    lgpio.spi_close(self.spi)
                self.spi = None
            
            # Close GPIO
            if self.using_rpi_gpio and GPIO_AVAILABLE:
                GPIO.cleanup()
            elif self.gpio_handle is not None:
                # Release claimed pins
                for pin, handle in self.pin_handles.items():
                    try:
                        lgpio.gpio_free(self.gpio_handle, pin)
                    except:
                        pass
                
                # Close GPIO chip
                try:
                    lgpio.gpiochip_close(self.gpio_handle)
                except:
                    pass
                    
                self.gpio_handle = None
                self.pin_handles = {}
            
            self.initialized = False
            print("Display resources freed")
        except Exception as e:
            print(f"Error closing display: {e}")
            # Don't raise an exception here, as this is cleanup code 