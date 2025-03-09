from managers.display_manager import DisplayManager

def main():
    try:
        display_manager = DisplayManager()
    except RuntimeError as e:
        print(f"Initialization failed: {e}")
        return

    try:
        display_manager.clear_screen()
    except Exception as e:
        print(f"Failed to clear the display: {e}")

    try:
        display_manager.display_text("Hello, E-Ink World!")
    except Exception as e:
        print(f"Failed to display text: {e}")

    try:
        display_manager.display_image_from_file('path/to/image.png')
    except Exception as e:
        print(f"Failed to display image: {e}")

    try:
        total_pixels = display_manager.eink_device.driver.width * display_manager.eink_device.driver.height
        image_bytes = [0xFF] * (total_pixels // 8)

        display_manager.display_bytes(image_bytes)
        print("Displayed raw byte data on E-Ink screen.")
    except Exception as e:
        print(f"Failed to display byte data: {e}")

if __name__ == "__main__":
    main()