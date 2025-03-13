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
RST_PIN = 17
DC_PIN = 25
CS_PIN = 8
BUSY_PIN = 24

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
        self.mock_mode = False
        self.using_rpi_gpio = False
        self.hardware_type = self._detect_hardware()
        self.handle_errors = os.environ.get('EINK_HANDLE_ERRORS', '1') == '1'
        
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
            
        if not os.path.exists('/dev/spidev0.0'):
            raise GPIOError("SPI device not available: /dev/spidev0.0")
            
        # Check permissions
        if not os.access('/dev/gpiochip0', os.R_OK | os.W_OK):
            raise GPIOError("No permission to access /dev/gpiochip0")
            
        if not os.access('/dev/spidev0.0', os.R_OK | os.W_OK):
            raise GPIOError("No permission to access /dev/spidev0.0")
        
        try:
            # Check if GPIO pins are already in use
            busy_pins, processes = self._check_conflicting_gpio_usage()
            if busy_pins and processes:
                print(f"Warning: GPIO pins {busy_pins} may be in use by processes: {', '.join(processes)}")
                # Continue anyway, but this might fail
            
            # For Raspberry Pi 5, we use lgpio
            if self.hardware_type == 'pi5' and LGPIO_AVAILABLE:
                print("Using Pi 5 compatible GPIO (gpiod) and SPI")
                self.gpio_handle = lgpio.gpiochip_open(0)
                
                # Configure pins
                for pin in [RST_PIN, DC_PIN, CS_PIN]:
                    handle = lgpio.gpio_claim_output(self.gpio_handle, pin, 0)
                    self.pin_handles[pin] = handle
                
                # Configure BUSY pin as input
                handle = lgpio.gpio_claim_input(self.gpio_handle, BUSY_PIN)
                self.pin_handles[BUSY_PIN] = handle
                
                # Open SPI device
                self.spi = lgpio.spi_open(0, 0, 10000000, 0)  # 10MHz, mode 0
                print("SPI and GPIO initialized with lgpio")
                
            # For other Raspberry Pi, use RPi.GPIO
            elif GPIO_AVAILABLE:
                print("Using RPi.GPIO for older Raspberry Pi")
                # Set up GPIO pins
                GPIO.setup(RST_PIN, GPIO.OUT)
                GPIO.setup(DC_PIN, GPIO.OUT)
                GPIO.setup(CS_PIN, GPIO.OUT)
                GPIO.setup(BUSY_PIN, GPIO.IN)
                
                # Initialize SPI using spidev
                import spidev
                self.spi = spidev.SpiDev()
                self.spi.open(0, 0)
                self.spi.max_speed_hz = 10000000  # 10MHz
                self.spi.mode = 0
                self.using_rpi_gpio = True
                print("SPI and GPIO initialized with RPi.GPIO")
                
            else:
                raise GPIOError("No suitable GPIO/SPI library available")
                
        except Exception as e:
            error_msg = f"Error setting up GPIO/SPI: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            # Clean up any partially initialized resources
            self.close()
            
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
    
    def send_command(self, command):
        """Send a command to the display"""
        if self.mock_mode:
            print(f"Mock send command: {command:#x}")
            return
            
        try:
            self._digital_write(DC_PIN, 0)
            self._digital_write(CS_PIN, 0)
            
            if self.using_rpi_gpio:
                self.spi.writebytes([command])
            else:
                lgpio.spi_write(self.spi, [command])
                
            self._digital_write(CS_PIN, 1)
        except Exception as e:
            error_msg = f"Error sending command {command:#x}: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after SPI error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def send_data(self, data):
        """Send data to the display"""
        if self.mock_mode:
            print(f"Mock send data: {data:#x}")
            return
            
        try:
            self._digital_write(DC_PIN, 1)
            self._digital_write(CS_PIN, 0)
            
            if self.using_rpi_gpio:
                self.spi.writebytes([data])
            else:
                lgpio.spi_write(self.spi, [data])
                
            self._digital_write(CS_PIN, 1)
        except Exception as e:
            error_msg = f"Error sending data {data:#x}: {str(e)}"
            print(error_msg)
            
            if self.handle_errors:
                # Fall back to mock mode
                print("Falling back to mock mode after SPI error")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def wait_until_idle(self):
        """Wait until the display is idle (not busy)"""
        if self.mock_mode:
            print("Mock wait until idle")
            time.sleep(0.1)  # Simulate a short delay
            return
            
        try:
            # Wait for busy pin to be high (not busy)
            print("Waiting for display to be ready...")
            start_time = time.time()
            while self._digital_read(BUSY_PIN) == 0:
                time.sleep(0.1)
                if time.time() - start_time > 10:  # Timeout after 10 seconds
                    print("Warning: Busy timeout, continuing anyway")
                    break
        except Exception as e:
            error_msg = f"Error waiting for display: {str(e)}"
            print(error_msg)
            
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
            
            # Load a font
            try:
                font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                       'resources', 'fonts', 'FreeSans.ttf')
                if not os.path.exists(font_path):
                    print(f"Font not found at {font_path}, using default")
                    font = ImageFont.load_default()
                else:
                    font = ImageFont.truetype(font_path, font_size)
            except:
                print("Error loading font, using default")
                font = ImageFont.load_default()
            
            # Draw the text
            draw.text((x, y), text, font=font, fill=0)
            
            # Display the image
            self.display(image)
        except Exception as e:
            error_msg = f"Error displaying text: {str(e)}"
            print(error_msg)
            
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